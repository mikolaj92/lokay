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

from lokay.organ.publication_gates import (
    _test_local_ok, _finalize_local_tests_ok, _test_local_probe,
    _require_test_local, _require_push, _require_real_diff,
    _require_acceptance, _require_publish_gate,
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

def localize_parent_route(out: dict[str, Any] | None) -> dict[str, Any]:
    """Always ok=true. Fala unblocks children of failed, so empty/timeout is a route."""
    blob = dict(out or {})
    nested = blob.get("result") if isinstance(blob.get("result"), dict) else {}
    raw = blob.get("paths")
    if not isinstance(raw, list):
        raw = nested.get("paths") if isinstance(nested.get("paths"), list) else []
    paths = [str(item).strip() for item in raw if str(item or "").strip()]
    if paths:
        return {**blob, "ok": True, "route": "ready", "paths": paths}
    reason = str(blob.get("reason") or nested.get("reason") or "")
    error = str(blob.get("error") or nested.get("error") or "")
    if "timed out" in error.lower() or reason in {"adapter_timeout", "timeout"}:
        reason = "localize_timeout"
    elif not reason:
        reason = "localize_empty"
    return {
        "ok": True,
        "route": "empty",
        "reason": reason,
        "paths": [],
        "error": error or "localize produced no edit paths",
    }

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
    from lokay.atom_runtime import run_atom_main

    return run_atom_main(module_main, argv)

def _cfg_flags(inputs: dict[str, Any]) -> list[str]:
    path = inputs.get("config_path") or inputs.get("config")
    return ["--config", str(path)] if path else []

def _live_flags(inputs: dict[str, Any]) -> list[str]:
    return ["--live"] if inputs.get("live") else []

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


def _merged_pr_payload(probe: dict[str, Any] | None) -> dict[str, Any] | None:
    """Refuse envelope when a probed PR is MERGED (or CLOSED). None = still open."""
    if not isinstance(probe, dict) or not probe:
        return None
    route = str(probe.get("route") or "")
    state = str(probe.get("state") or "").upper()
    merged = bool(probe.get("merged")) or route == "merged" or state == "MERGED"
    if merged:
        reason = "pr_already_merged"
        state_out = "MERGED"
    elif route == "closed" or state == "CLOSED":
        reason = "pr_closed"
        state_out = "CLOSED"
    else:
        return None
    return {
        "ok": False,
        "error": f"refusing: PR {probe.get('repo') or ''}#{probe.get('pr') or ''} is {state_out}",
        "reason": reason,
        "pr_state": state_out,
        "pr": probe.get("pr"),
        "repo": probe.get("repo"),
        "route": "skip",
    }


def _pr_already_merged(
    up: dict[str, dict[str, Any]],
    *,
    cfg: list[str] | None = None,
    live: list[str] | None = None,
    repo: str = "",
    pr_number: int | None = None,
    run=None,
    probe_main=None,
) -> dict[str, Any] | None:
    """Stop pr_repair mutations when the target PR is already MERGED.

    Admission can race with Alfred merge. Re-view live before mutating atoms.
    Gh flake stays fail-open (same as ``_issue_no_longer_open``).
    """
    for key in ("admit_pr_repair", "probe_pr_state"):
        blob = up.get(key) or {}
        if isinstance(blob, dict) and blob:
            refused = _merged_pr_payload(blob)
            if refused is not None:
                return refused
    if live is None or "--live" not in live:
        return None
    if not repo or pr_number is None or run is None or probe_main is None:
        return None
    try:
        viewed = run(
            probe_main,
            [*(cfg or []), *live, "--repo", str(repo), "--pr", str(pr_number)],
        )
    except Exception:
        return None
    if not isinstance(viewed, dict):
        return None
    if viewed.get("ok") is False:
        return None  # fail-open on probe hard-fail
    return _merged_pr_payload(viewed)


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
    from lokay.atom_runtime import run_atom_main

    run = run_atom_main
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

