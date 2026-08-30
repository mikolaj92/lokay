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


def handle_factory(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue,
        close_issue,
        commit_all,
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
        reap_stale_implementing,
        reap_stale_worktrees,
        refresh_occupancy,
        compact_state,
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

    if atom == "factory_tick":
        # Legacy alias (not in parent factory_pass). Invokes the same Fala
        # factory_pass mill as lokay-factory-pass — not an in-process spine.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}

    if atom == "classify_factory_idle":
        from lokay.proc.classify_factory_idle import classify

        return classify(live=bool(inputs.get("live")))

    if atom == "record_factory_idle":
        from lokay.proc.record_factory_idle import record

        return record(
            up.get("classify_factory_idle") or {},
            config_path=str(inputs.get("config_path") or "") or None,
        )

    if atom == "factory_pass_terminal":
        from lokay.proc.factory_pass_terminal import terminal

        return terminal(up.get("record_pass") or {})

    if atom == "host_ff":
        from lokay.git_host_ff import snapshot_process_head

        argv = [*cfg, *live]
        checkout = inputs.get("checkout") or os.environ.get("LOKAY_ROOT")
        if checkout:
            argv.extend(["--checkout", str(checkout)])
        out = _run_atom_main(host_ff.main, argv)
        if checkout and out.get("ok"):
            snapshot_process_head(Path(str(checkout)), refresh=True)
        return out

    if atom == "factory_begin_host_gate":
        from lokay.proc.gate_factory_begin_host import gate

        return gate(
            up.get("host_ff") or {},
            live=bool(inputs.get("live")),
            checkout=str(inputs.get("checkout") or os.environ.get("LOKAY_ROOT") or ""),
        )

    if atom == "factory_begin":
        from lokay.proc.factory_begin_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "survey_repos":
        # Legacy bridge atom (not in parent factory_pass graph).
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(survey_repos.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "survey_prs":
        from lokay.proc.survey_prs_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "survey_inbox":
        from lokay.proc.survey_inbox_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "survey_ready":
        from lokay.proc.survey_ready_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "ready_hygiene":
        from lokay.proc.ready_hygiene_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "plan_pass":
        from lokay.proc.plan_pass_subflow import run

        pass_dir = str(
            up.get("factory_begin", {}).get("pass_dir")
            or up.get("survey_ready", {}).get("pass_dir")
            or up.get("survey_repos", {}).get("pass_dir")
            or ""
        )
        assert pass_dir
        return run(pass_dir=pass_dir)

    if atom == "dispatch_triage":
        from lokay.proc.dispatch_triage_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "resolve_conflicts":
        from lokay.proc.resolve_conflicts_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "closeout_prs":
        from lokay.proc.closeout_prs_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "reap_stale_implementing":
        from lokay.proc.reap_stale_implementing_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "") or None
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "reap_over_budget":
        from lokay.proc.reap_over_budget_subflow import run
        from lokay.proc.pi_budget import DEFAULT_BUDGET_S

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "") or None
        return run(
            budget_s=DEFAULT_BUDGET_S,
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "refresh_occupancy":
        from lokay.proc.refresh_occupancy_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "reap_stale_worktrees":
        from lokay.proc.reap_stale_worktrees_subflow import run

        return run(
            pass_dir=str(up.get("factory_begin", {}).get("pass_dir") or ""),
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "select_implement":
        from lokay.proc.select_implement_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        out = run(pass_dir=pass_dir)
        route = str(out.get("route") or "none")
        # Parent when is binary: selected work vs housecleaning (none / no_budget).
        if route != "selected":
            route = "none"
        return {**out, "route": route}

    if atom == "queue_conflict":
        from lokay.proc.queue_conflict_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "dispatch_implement":
        from lokay.proc.dispatch_implementation_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "compute_health":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            compute_health.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "record_pass":
        begin = up.get("factory_begin") or {}
        gate = up.get("factory_begin_host_gate") or {}
        out = record_pass.record(
            pass_dir=str(begin.get("pass_dir") or ""),
            begin=begin,
            prs=up.get("run_pr_triage_department")
            or up.get("run_pr_repair_department")
            or {},
            issues=up.get("run_issue_triage_department")
            or up.get("run_executor_department")
            or {},
            leftover=up.get("leftover_catalog") or up.get("leftover") or {},
        )
        if str(gate.get("route") or "") == "restart":
            result = dict(out.get("result") or {})
            result.update(
                health="host_updated",
                reason="host_updated",
                restart_required=True,
                idle=False,
            )
            out = {
                **out,
                "health": "host_updated",
                "reason": "host_updated",
                "restart_required": True,
                "result": result,
                "tick": {**(out.get("tick") or {}), **result},
            }
        return out

    if atom == "compact_state":
        return _run_atom_main(compact_state.main, [*cfg])

    return None
