"""Fala organ routing — one job family per module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.prompts import (
    self_repair_prompt,
)


def _fail_closed_skip(*, reason: str, **extra: Any) -> dict[str, Any]:
    """ok=True skipped envelope so organ_envelope never aborts the path."""
    out: dict[str, Any] = {
        "ok": True,
        "skipped": True,
        "route": "fail_closed",
        "reason": reason,
    }
    out.update(extra)
    return out


def _reclaim_validate_journal_soft() -> None:
    """Reap incomplete self_repair journals after validate; never raise."""
    try:
        from lokay.fala_journal import reclaim_self_repair_incomplete_journals

        reclaim_self_repair_incomplete_journals()
    except Exception:
        return


def handle_self_repair(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        commit_all,
        run_agent,
        self_repair_close,
        self_repair_preflight,
        self_repair_push_main,
    )

    cfg = ctx["cfg"]
    live = ctx["live"]
    issue_number = ctx["issue_number"]

    from lokay.atom_runtime import run_atom_main

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main
    if atom == "summarize_self_repair":
        from lokay.proc.summarize_self_repair import summarize

        return summarize(
            preflight=up.get("self_repair_preflight") or {},
            push=up.get("self_repair_push_main") or {},
            activate=up.get("self_repair_activate") or {},
            close=up.get("self_repair_close") or {},
        )

    if atom == "self_repair_prepare":
        from lokay.proc.self_repair_prepare_subflow import run

        fingerprint = str(inputs.get("fingerprint") or "")
        assert fingerprint
        return run(
            fingerprint=fingerprint,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "self_repair_run_agent":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main") or prepared.get("resumed"):
            return {
                "ok": True,
                "skipped": True,
                "reason": (
                    "already_on_main"
                    if prepared.get("already_on_main")
                    else "resume_existing_candidate"
                ),
                "commit": prepared.get("commit") or prepared.get("candidate_commit"),
            }
        worktree = str(prepared.get("worktree") or "")
        issue_raw = inputs.get("incident") or {}
        issue = Issue.from_dict(issue_raw) if isinstance(issue_raw, dict) else None
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and issue is not None and fingerprint
        prompt = self_repair_prompt(
            issue=issue,
            fingerprint=fingerprint,
            evidence=str(inputs.get("failure_evidence") or ""),
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(prompt)
            prompt_path = fh.name
        try:
            return _run_atom_main(
                run_agent.main,
                [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)

    if atom == "self_repair_validate":
        from lokay.proc.self_repair_validate_subflow import run

        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main"):
            return {
                "ok": True,
                "skipped": True,
                "validated": True,
                "reason": "already_on_main",
            }
        committed = up.get("self_repair_commit", {})
        worktree = str(prepared.get("worktree") or "")
        base_sha = str(prepared.get("base_sha") or "")
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and base_sha and fingerprint and committed.get("commit")
        try:
            result = run(
                worktree=worktree,
                base_sha=base_sha,
                expected_subject=f"self-repair: {fingerprint}",
                expected_commit=str(committed["commit"]),
            )
        finally:
            _reclaim_validate_journal_soft()
        if not isinstance(result, dict):
            return _fail_closed_skip(
                reason="validate_non_dict",
                validated=False,
                error="self_repair_validate returned non-dict",
            )
        if result.get("validated") is not True:
            reason = str(
                result.get("reason")
                or result.get("error")
                or result.get("route")
                or "not_validated"
            )
            return {
                "ok": True,
                "validated": False,
                "route": "fail_closed",
                "reason": reason,
                "error": result.get("error") or reason,
                "commit": result.get("commit") or committed.get("commit"),
            }
        return result

    if atom == "self_repair_commit":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main") or prepared.get("candidate_commit"):
            return {
                "ok": True,
                "skipped": True,
                "reason": (
                    "already_on_main"
                    if prepared.get("already_on_main")
                    else "resume_committed_candidate"
                ),
                "commit": prepared.get("commit") or prepared.get("candidate_commit"),
            }
        worktree = str(prepared.get("worktree") or "")
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and fingerprint
        return _run_atom_main(
            commit_all.main,
            [
                *cfg,
                *live,
                "--worktree",
                worktree,
                "--message",
                f"self-repair: {fingerprint}",
            ],
        )

    if atom == "self_repair_push_main":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_on_main",
                "commit": prepared.get("commit"),
                "pushed": False,
            }
        validated = up.get("self_repair_validate", {})
        committed = up.get("self_repair_commit", {})
        worktree = str(prepared.get("worktree") or "")
        base_sha = str(prepared.get("base_sha") or "")
        expected_commit = str(committed.get("commit") or "")
        validated_commit = str(validated.get("commit") or "")
        if (
            not worktree
            or not base_sha
            or not expected_commit
            or validated_commit != expected_commit
            or validated.get("validated") is not True
        ):
            reason = (
                "not_validated"
                if validated.get("validated") is not True
                else "commit_mismatch"
            )
            return _fail_closed_skip(
                reason=reason,
                pushed=False,
                commit=expected_commit or validated_commit or None,
            )
        return _run_atom_main(
            self_repair_push_main.main,
            [
                *cfg,
                *live,
                "--worktree",
                worktree,
                "--base-sha",
                base_sha,
                "--validated",
                "--expected-commit",
                validated_commit,
            ],
        )

    if atom == "self_repair_activate":
        prepared = up.get("self_repair_prepare", {})
        pushed = up.get("self_repair_push_main", {})
        commit = str(pushed.get("commit") or prepared.get("commit") or "")
        fail_closed = pushed.get("route") == "fail_closed" or (
            pushed.get("skipped") and pushed.get("reason") != "already_on_main"
        )
        if fail_closed or not commit:
            return _fail_closed_skip(
                reason=str(pushed.get("reason") or "missing_commit"),
                commit=commit or None,
            )
        from lokay.proc.self_repair_activate_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            commit=commit,
        )

    if atom == "self_repair_preflight":
        activated = up.get("self_repair_activate", {})
        commit = str(activated.get("commit") or "")
        project = str(activated.get("path") or "")
        config_path = str(inputs.get("config_path") or inputs.get("config") or "")
        if (
            activated.get("skipped")
            or activated.get("route") == "fail_closed"
            or not commit
            or not project
            or not config_path
        ):
            return _fail_closed_skip(
                reason=str(activated.get("reason") or "activate_skipped"),
                commit=commit or None,
                validated=False,
            )
        return _run_atom_main(
            self_repair_preflight.main,
            ["--config", config_path, "--project", project, "--commit", commit],
        )

    if atom == "self_repair_close":
        preflight = up.get("self_repair_preflight", {})
        commit = str(preflight.get("commit") or "")
        if (
            issue_number is None
            or not commit
            or preflight.get("skipped")
            or preflight.get("route") == "fail_closed"
            or preflight.get("validated") is False
        ):
            return _fail_closed_skip(
                reason=str(preflight.get("reason") or "preflight_skipped"),
                closed=False,
                commit=commit or None,
            )
        return _run_atom_main(
            self_repair_close.main,
            [*cfg, *live, "--issue", str(issue_number), "--commit", commit],
        )

    return None
