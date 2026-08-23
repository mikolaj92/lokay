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
        reap_stale_implementing,
        reap_stale_worktrees,
        refresh_occupancy,
        ready_hygiene,
        compact_state,
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

    if atom == "factory_tick":
        # Legacy alias (not in parent factory_pass). Invokes the same Fala
        # factory_pass mill as lokay-factory-pass — not an in-process spine.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}

    if atom == "host_ff":
        argv = [*cfg, *live]
        checkout = inputs.get("checkout") or os.environ.get("LOKAY_ROOT")
        if checkout:
            argv.extend(["--checkout", str(checkout)])
        return _run_atom_main(host_ff.main, argv)

    if atom == "factory_begin":
        # In-cycle host_ff updates git; this process still imported the
        # previous package and the Fala graph is already materialized.
        # Refuse product work so the next launchd tick reinstalls.
        # Launchd-ff under mill.lock can eat updated=true; then HEAD
        # moved under LOKAY_PROCESS_HEAD and we still refuse.
        from lokay.git_host_ff import process_head_moved

        host = up.get("host_ff") or {}
        if "--live" in live and host.get("updated") is True:
            return {
                "ok": False,
                "error": "host checkout updated; restart required before product work",
                "reason": "host_updated",
                "health": "host_updated",
                "restart_required": True,
                "head": host.get("head"),
                "origin_main": host.get("origin_main"),
            }
        checkout = inputs.get("checkout") or os.environ.get("LOKAY_ROOT")
        moved = process_head_moved(Path(str(checkout))) if checkout else None
        if "--live" in live and moved is not None:
            return moved
        return _run_atom_main(factory_begin.main, [*cfg, *live])

    if atom == "survey_repos":
        # Legacy bridge atom (not in parent factory_pass graph).
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(survey_repos.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "survey_prs":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(survey_prs.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "survey_inbox":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(survey_inbox.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "survey_ready":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(survey_ready.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "ready_hygiene":
        return _run_atom_main(ready_hygiene.main, [*cfg, *live])

    if atom == "plan_pass":
        pass_dir = str(
            up.get("factory_begin", {}).get("pass_dir")
            or up.get("survey_ready", {}).get("pass_dir")
            or up.get("survey_repos", {}).get("pass_dir")
            or ""
        )
        assert pass_dir
        return _run_atom_main(plan_pass.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "dispatch_triage":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            dispatch_triage.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "resolve_conflicts":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            resolve_conflicts.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "closeout_prs":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(closeout_prs.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "reap_stale_implementing":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        argv = [*cfg, *live]
        if pass_dir:
            argv.extend(["--pass-dir", pass_dir])
        return _run_atom_main(reap_stale_implementing.main, argv)

    if atom == "reap_over_budget":
        from lokay.proc import reap_over_budget

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        argv = [*cfg, *live]
        if pass_dir:
            argv.extend(["--pass-dir", pass_dir])
        return _run_atom_main(reap_over_budget.main, argv)

    if atom == "refresh_occupancy":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            refresh_occupancy.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "reap_stale_worktrees":
        from lokay.proc.reap_stale_worktrees_subflow import run

        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return run(
            pass_dir=pass_dir,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "select_implement":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            select_implement.main, [*cfg, *live, "--pass-dir", pass_dir]
        )

    if atom == "queue_conflict":
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        return _run_atom_main(
            queue_conflict.main, [*cfg, *live, "--pass-dir", pass_dir]
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
        pass_dir = str(up.get("factory_begin", {}).get("pass_dir") or "")
        assert pass_dir
        # Domain health (stall/work_remaining) is successful conduction; the
        # tick envelope inside may still set ok=false for the mill.
        return _run_atom_main(record_pass.main, [*cfg, *live, "--pass-dir", pass_dir])

    if atom == "compact_state":
        return _run_atom_main(compact_state.main, [*cfg])

    return None
