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
        recovery_factory,
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

    from lokay.atom_runtime import run_atom_main
    from lokay.git_commit import branch_ahead_of_upstream as _branch_ahead

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main
    branch_ahead_of_upstream = ctx.get("branch_ahead_of_upstream") or _branch_ahead
    known = False

    if atom == "summarize_daemon_cycle":
        from lokay.proc.summarize_daemon_cycle import summarize

        return summarize(
            lokay_node=up.get("recovery_factory") or {},
            repair=up.get("recovery_run_self_repair") or {},
        )

    if atom == "last_pass_moving":
        from lokay.proc import last_pass_moving

        return _run_atom_main(last_pass_moving.main, [*cfg, *live])

    if atom == "select_repair_route":
        import argparse

        from lokay.pass_receipt import read_pass_receipt
        from lokay.proc._common import load_cfg
        from lokay.proc.last_pass_moving import classify as classify_moving
        from lokay.proc.leftover_skip import classify as leftover_classify
        from lokay.proc.select_repair_route import select

        config_path = str(inputs.get("config_path") or inputs.get("config") or "")
        loaded = load_cfg(argparse.Namespace(config=config_path or None))
        receipt = read_pass_receipt(state_path=loaded.state_path)
        moving = up.get("last_pass_moving") or classify_moving(receipt)
        leftover = up.get("leftover_skip") or leftover_classify(receipt)
        enabled = bool(getattr(loaded, "department_self_repair", True))
        return select(moving, leftover, receipt, enabled=enabled)

    if atom == "recovery_begin":
        return _run_atom_main(recovery_begin.main, [*cfg, *live])

    if atom == "recovery_factory":
        return _run_atom_main(
            recovery_factory.main,
            [*cfg, *live, "--max-passes", str(int(inputs.get("max_passes") or 8))],
        )

    if atom == "recovery_observe":
        begin = up.get("recovery_begin", {})
        lokay = up.get("recovery_factory", {}).get("factory")
        assert begin.get("state_path") and lokay is not None
        return _run_atom_main(
            recovery_observe.main,
            [
                "--state-path",
                str(begin["state_path"]),
                "--state-offset",
                str(begin.get("state_offset") or 0),
                "--lokay-json",
                json.dumps(lokay, ensure_ascii=False),
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
        classified = up.get("select_repair_route") or {}
        if classified.get("route") != "repair":
            return {
                "ok": True,
                "skipped": True,
                "reason": classified.get("reason") or "factory",
            }
        return _run_atom_main(
            recovery_incident.main,
            [
                "--fingerprint",
                str(classified.get("fingerprint") or "did_not_move"),
                "--evidence",
                str(classified.get("evidence") or ""),
            ],
        )

    if atom == "recovery_run_self_repair":
        classified = up.get("select_repair_route") or {}
        if classified.get("route") != "repair":
            return {
                "ok": True,
                "skipped": True,
                "reason": classified.get("reason") or "factory",
            }
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
