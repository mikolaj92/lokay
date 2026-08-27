"""Shared Fala organ helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fala import sdk

from lokay.git_commit import branch_ahead_of_upstream
from lokay.models import Issue
from lokay.proc._common import runner
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
    self_repair_prompt,
    timeout_resume_prompt,
)


def _request_blob(up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return dict(
        up.get("prepare_coding_request")
        or up.get("prepare_local_repair_request")
        or {}
    )


def _worktree_path(
    up: dict[str, dict[str, Any]], inputs: dict[str, Any] | None = None
) -> str:
    return str(
        (up.get("worktree_add") or {}).get("worktree")
        or _request_blob(up).get("worktree")
        or (inputs or {}).get("worktree")
        or ""
    )


def _issue_raw(
    up: dict[str, dict[str, Any]], inputs: dict[str, Any] | None = None
) -> dict[str, Any]:
    raw = (up.get("get_issue") or {}).get("issue")
    if isinstance(raw, dict) and raw:
        return dict(raw)
    blob = _request_blob(up).get("issue_raw")
    if isinstance(blob, dict) and blob:
        return dict(blob)
    extra = (inputs or {}).get("issue_raw")
    return dict(extra) if isinstance(extra, dict) else {}


def _localize_conduction(
    up: dict[str, dict[str, Any]], inputs: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    if "localize" in up:
        return up
    loc = _request_blob(up).get("localize") or (inputs or {}).get("localize") or {}
    return {**up, "localize": dict(loc) if isinstance(loc, dict) else {}}


def _localize_paths(up: dict[str, dict[str, Any]]) -> list[str]:
    """Paths from localize conduction; empty means fail-closed before agent."""
    raw = up.get("localize", {}).get("paths") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        rel = str(item or "").strip()
        if rel:
            out.append(rel)
    return out


def _conduction_values(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map upstream step id → its values dict."""
    raw = sdk.conduction(manifest)
    out: dict[str, dict[str, Any]] = {}
    for step_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        values = payload.get("values")
        if isinstance(values, dict):
            out[str(step_id)] = values
        else:
            # some hosts pass values at top level
            out[str(step_id)] = payload
    return out


def _run_atom_main(module_main, argv: list[str]) -> dict[str, Any]:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module_main(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty atom stdout", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def _cfg_flags(inputs: dict[str, Any]) -> list[str]:
    path = inputs.get("config_path") or inputs.get("config")
    return ["--config", str(path)] if path else []


def _live_flags(inputs: dict[str, Any]) -> list[str]:
    return ["--live"] if inputs.get("live") else []


def _test_local_ok(env: dict[str, Any] | None) -> bool:
    """Green suite, or an honest skip (no Python suite), counts as success.

    A recorded-red first probe (`ok: true, passed: false`) is NOT success —
    that envelope exists only so Fala can conduct the one-shot repair nest.
    """
    if not isinstance(env, dict) or not env:
        return False
    if env.get("route") == "pass":
        return True
    if env.get("passed") is False:
        return False
    if env.get("skipped") or env.get("reason") == "no_python_test_suite":
        return True
    return env.get("ok") is True


def _closed_issue_payload(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Refuse envelope when a viewed issue is not OPEN. None means still open."""
    if not isinstance(raw, dict) or not raw:
        return None
    state = str(raw.get("state") or "OPEN").upper()
    if state == "OPEN":
        return None
    number = raw.get("number")
    repo = str(raw.get("repo") or "")
    return {
        "ok": False,
        "error": f"refusing: issue {repo}#{number} is {state}",
        "reason": "issue_closed",
        "issue_state": state,
        "issue": number,
        "repo": repo,
    }


def _issue_no_longer_open(
    up: dict[str, dict[str, Any]],
    *,
    cfg: list[str] | None = None,
    live: list[str] | None = None,
    repo: str = "",
    issue_number: int | None = None,
    run=None,
    get_issue_main=None,
) -> dict[str, Any] | None:
    """Stop coding / publishing when the ticket is no longer OPEN.

    ``get_issue`` runs at the start of issue_to_pr. A sibling (human, Codex)
    can close it during the 1800s slot; timeout-resume and pr_create must
    re-view live, not trust that stale conduction. Gh flake stays fail-open
    so a blip does not abort a still-open ticket. ``issue not found`` is closed.
    """
    raw = up.get("get_issue", {}).get("issue")
    refused = _closed_issue_payload(raw if isinstance(raw, dict) else None)
    if refused is not None:
        return refused
    if live is None or "--live" not in live:
        return None
    if not repo or issue_number is None or run is None or get_issue_main is None:
        return None
    try:
        viewed = run(
            get_issue_main,
            [*(cfg or []), *live, "--repo", str(repo), "--issue", str(issue_number)],
        )
    except Exception:
        return None
    if not isinstance(viewed, dict):
        return None
    if viewed.get("ok") is False:
        err = str(viewed.get("error") or "").lower()
        if "not found" in err:
            return {
                "ok": False,
                "error": f"refusing: issue {repo}#{issue_number} is missing",
                "reason": "issue_closed",
                "issue_state": "MISSING",
                "issue": issue_number,
                "repo": repo,
            }
        return None
    issue = viewed.get("issue")
    return _closed_issue_payload(issue if isinstance(issue, dict) else None)


def _require_test_local(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_merge/pr_create need successful local tests.

    Delivery-lane publish (`finalize_local_tests.route == publish`) is already
    on issue_to_pr_delivery push/pr_create conduction and is the verdict when
    present. A skipped first-probe key must not wipe that. pr_repair/pr_triage
    have no finalize node, so the first probe still gates.

    The issue_to_pr lane adds one bounded recheck (test_local_recheck or
    local_repair_execution) after the single repair patch. When that
    conduction exists, it is the verdict (a recorded-red first probe is
    expected — that is why the nest ran).
    Missing key, ok:false, or a red suite returns an error envelope. None means go.
    """
    finalize = up.get("finalize_local_tests")
    if isinstance(finalize, dict) and finalize.get("route") == "publish":
        return None
    first = up.get("test_local")
    if first is None:
        first = up.get("test_local_execution")
    if first is None:
        return {
            "ok": False,
            "error": "refusing: test_local conduction missing",
            "reason": "test_local_missing",
        }
    recheck = up.get("test_local_recheck")
    if not isinstance(recheck, dict) or not recheck:
        repair = up.get("local_repair_execution")
        if isinstance(repair, dict) and repair.get("route") in {
            "pass",
            "fail",
            "terminal",
        }:
            recheck = repair
        else:
            recheck = None
    if recheck is not None:
        if _test_local_ok(recheck):
            return None
        return {
            "ok": False,
            "error": str(
                recheck.get("error")
                or "refusing: test_local_recheck did not succeed"
            ),
            "reason": "test_local_recheck_failed",
        }
    tl = first
    if not _test_local_ok(tl):
        return {
            "ok": False,
            "error": str(tl.get("error") or "refusing: test_local did not succeed"),
            "reason": "test_local_failed",
        }
    return None


def _require_push(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: pr_create only after a successful push conduction.

    A red local suite or a refused/failed push must never reach
    `gh pr create`. None means go.
    """
    push = up.get("push")
    if push is None:
        return {
            "ok": False,
            "error": "refusing: push conduction missing",
            "reason": "push_missing",
        }
    if push.get("ok") is not True:
        return {
            "ok": False,
            "error": str(push.get("error") or "refusing: push did not succeed"),
            "reason": "push_failed",
        }
    return None


def _require_real_diff(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_create need a real (non-plan-only) diff.

    Plan/localize evidence (``.lokay/approach.md``, ``.lokay/localize.json``)
    is not progress. Missing key or ok:false returns an error envelope.
    None means go.
    """
    env = up.get("assert_real_diff")
    if env is None:
        return {
            "ok": False,
            "error": "refusing: assert_real_diff conduction missing",
            "reason": "real_diff_missing",
        }
    if env.get("ok") is not True:
        return {
            "ok": False,
            "error": str(env.get("error") or "refusing: diff is not real progress"),
            "reason": str(env.get("reason") or "plan_only"),
        }
    return None


def _resume_after_timeout(
    *,
    run_agent_main,
    assert_real_diff_main,
    commit_all_main,
    cfg: list[str],
    live: list[str],
    inputs: dict[str, Any],
    worktree: str,
    repo: str,
    branch: str,
    issue_number: int | None,
    issue_raw: dict[str, Any],
    get_issue_main=None,
) -> dict[str, Any]:
    """One continue pass on the same corner after executor timeout."""
    import lokay.fala_organ as _fo

    run = getattr(_fo, "_run_atom_main", _run_atom_main)
    refused = _issue_no_longer_open(
        {"get_issue": {"issue": issue_raw or {}}},
        cfg=cfg,
        live=live,
        repo=repo,
        issue_number=issue_number,
        run=run,
        get_issue_main=get_issue_main,
    )
    if refused is not None:
        return refused
    prompt = timeout_resume_prompt(
        repo=repo,
        branch=branch,
        issue_number=issue_number,
        issue_title=str(issue_raw.get("title") or ""),
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(prompt)
        prompt_path = fh.name
    try:
        out = run(
            run_agent_main,
            [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
        )
    finally:
        Path(prompt_path).unlink(missing_ok=True)
    if isinstance(out, dict):
        out["attempted"] = True
        out["reason"] = "timeout_resume"
    if inputs.get("live") and isinstance(out, dict) and out.get("ok") is not False:
        gate = run(assert_real_diff_main, ["--worktree", worktree])
        if isinstance(gate, dict) and gate.get("real") is True:
            n = issue_raw.get("number", issue_number)
            title = str(issue_raw.get("title") or "")[:60]
            msg = f"fix: {repo}#{n} {title}".strip()
            committed = run(
                commit_all_main,
                [*cfg, *live, "--worktree", worktree, "--message", msg],
            )
            if isinstance(committed, dict):
                out["committed"] = committed.get("committed")
    return out


