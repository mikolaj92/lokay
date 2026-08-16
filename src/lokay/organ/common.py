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
    if env.get("passed") is False:
        return False
    if env.get("skipped") or env.get("reason") == "no_python_test_suite":
        return True
    return env.get("ok") is True


def _require_test_local(up: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fail-closed gate: push/pr_merge/pr_create need successful local tests.

    The issue_to_pr lane adds one bounded recheck (test_local_recheck) after
    the single repair patch. When that conduction exists, it is the verdict
    (a recorded-red first probe is expected — that is why the nest ran).
    pr_repair/pr_triage have no recheck node, so the first probe still gates.
    Missing key, ok:false, or a red suite returns an error envelope. None means go.
    """
    if "test_local" not in up:
        return {
            "ok": False,
            "error": "refusing: test_local conduction missing",
            "reason": "test_local_missing",
        }
    recheck = up.get("test_local_recheck")
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
    tl = up["test_local"]
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
) -> dict[str, Any]:
    """One continue pass on the same corner after executor timeout."""
    prompt = timeout_resume_prompt(
        repo=repo,
        branch=branch,
        issue_number=issue_number,
        issue_title=str(issue_raw.get("title") or ""),
    )
    import lokay.fala_organ as _fo

    run = getattr(_fo, "_run_atom_main", _run_atom_main)
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


