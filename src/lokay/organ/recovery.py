"""Fala organ routing — one job family per module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.common import (
    _cfg_flags,
    _live_flags,
    _localize_paths,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _run_atom_main,
    _test_local_ok,
)
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
    self_repair_prompt,
)


def handle_recovery(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue,
        close_issue,
        commit_all,
        closeout_prs,
        compute_health,
        cycle_end,
        cycle_start,
        dispatch_implement,
        dispatch_triage,
        factory_begin,
        factory_tick,
        get_issue,
        host_ff,
        list_prs,
        make_branch,
        plan_issue,
        localize,
        pi_budget,
        plan_pass,
        pr_checks,
        pr_create,
        pr_label,
        pr_merge,
        push_branch,
        record_pass,
        recovery_begin,
        recovery_incident,
        recovery_mill,
        recovery_observe,
        recovery_record,
        recovery_run_self_repair,
        resolve_conflicts,
        run_agent,
        select_implement,
        queue_conflict,
        stage_label,
        survey_inbox,
        survey_prs,
        survey_ready,
        survey_repos,
        test_local,
        worktree_add,
        assert_real_diff,
        self_repair_activate,
        self_repair_close,
        self_repair_prepare,
        self_repair_preflight,
        self_repair_push_main,
        self_repair_validate,
    )
    from lokay.stuck import issue_number_from_branch

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]

    import lokay.fala_organ as _fo

    _run_atom_main = _fo._run_atom_main
    branch_ahead_of_upstream = getattr(_fo, "branch_ahead_of_upstream", None)
    if branch_ahead_of_upstream is None:
        from lokay.git_commit import branch_ahead_of_upstream
    known = False

    if atom == "run_factory_pass":
        from lokay.compose.factory import compose_factory_pass

        return {
            "ok": True,
            "mill": compose_factory_pass(
                config_path=str(inputs.get("config_path") or "") or None,
                live=True,
            ),
        }

    if atom == "summarize_daemon_cycle":
        from lokay.proc.summarize_daemon_cycle import summarize

        return summarize(
            mill_node=up.get("run_factory_pass") or up.get("recovery_mill") or {},
            repair=up.get("recovery_run_self_repair") or {},
        )

    if atom == "recovery_begin":
        return _run_atom_main(recovery_begin.main, [*cfg, *live])

    if atom == "recovery_mill":
        return _run_atom_main(
            recovery_mill.main,
            [*cfg, *live, "--max-passes", str(int(inputs.get("max_passes") or 8))],
        )

    if atom == "recovery_observe":
        begin = up.get("recovery_begin", {})
        mill = up.get("recovery_mill", {}).get("mill")
        assert begin.get("state_path") and mill is not None
        return _run_atom_main(
            recovery_observe.main,
            [
                "--state-path",
                str(begin["state_path"]),
                "--state-offset",
                str(begin.get("state_offset") or 0),
                "--mill-json",
                json.dumps(mill, ensure_ascii=False),
            ],
        )

    if atom == "recovery_record":
        begin = up.get("recovery_begin", {})
        observation = up.get("recovery_observe", {}).get("observation")
        assert begin.get("state_path") and observation is not None
        return _run_atom_main(
            recovery_record.main,
            [
                "--state-path",
                str(begin["state_path"]),
                "--observation-json",
                json.dumps(observation, ensure_ascii=False),
            ],
        )

    if atom == "recovery_incident":
        recorded = up.get("recovery_record", {})
        if recorded.get("confirmed") is not True:
            return {"ok": True, "skipped": True, "reason": "stall_quorum_not_met"}
        recovery = recorded.get("recovery") or {}
        return _run_atom_main(
            recovery_incident.main,
            [
                "--fingerprint",
                str(recovery.get("fingerprint") or ""),
                "--evidence",
                str(recovery.get("evidence") or ""),
            ],
        )

    if atom == "recovery_run_self_repair":
        incident = up.get("recovery_incident", {})
        if incident.get("skipped"):
            return {"ok": True, "skipped": True, "reason": incident.get("reason")}
        assert incident.get("fingerprint") and incident.get("incident_url")
        return _run_atom_main(
            recovery_run_self_repair.main,
            [
                *cfg,
                "--fingerprint",
                str(incident["fingerprint"]),
                "--incident-url",
                str(incident["incident_url"]),
                "--evidence",
                str(incident.get("failure_evidence") or ""),
            ],
        )

    return None
