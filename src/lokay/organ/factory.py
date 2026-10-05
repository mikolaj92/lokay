"""Fala organ routing — one job family per module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def handle_factory(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        compact_state,
        compute_health,
        factory_tick,
        host_ff,
        record_pass,
    )

    cfg = ctx["cfg"]
    live = ctx["live"]

    from lokay.atom_runtime import run_atom_main

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main

    if atom == "factory_tick":
        # Legacy alias (not in parent factory_pass). Invokes the same Fala
        # factory_pass lokay as lokay-factory-pass — not an in-process spine.
        return {"ok": True, "tick": _run_atom_main(factory_tick.main, [*cfg, *live])}



    if atom == "factory_pass_terminal":
        from lokay.proc.factory_pass_terminal import terminal

        return terminal(up.get("record_pass") or {})

    if atom == "harvest_factory_children":
        from lokay.proc.harvest_factory_children import harvest

        return harvest(
            config={
                "state_path": str(inputs.get("state_path") or "") or None,
                "config_path": str(inputs.get("config_path") or "") or None,
                "live": bool(inputs.get("live", True)),
            },
            scope={
                "config_path": str(inputs.get("config_path") or "") or None,
                "repos": list(inputs.get("repos") or []),
            },
            ledger={},
        )

    if atom == "host_ff":
        from lokay.git_host_ff import snapshot_process_head

        argv = [*cfg, *live]
        checkout = inputs.get("checkout") or os.environ.get("LOKAY_ROOT")
        if checkout:
            argv.extend(["--checkout", str(checkout)])
        out = _run_atom_main(host_ff.main, argv)
        if checkout and out.get("ok"):
            snapshot_process_head(Path(str(checkout)), refresh=True)
        if out.get("ok") is not True:
            # Conduct the failed sync fact to the host gate; adapter errors
            # otherwise erase its named reason from the pass receipt.
            return {**out, "ok": True, "_exit": 0, "route": "blocked"}
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




    if atom == "ready_hygiene":
        from lokay.proc.ready_hygiene_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )


    if atom == "dispatch_triage":
        from lokay.proc.dispatch_triage_subflow import run

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
        if not begin.get("state_path") and inputs.get("config_path"):
            from lokay.config import load_config

            begin = {**begin, "state_path": str(load_config(inputs["config_path"]).state_path)}
        begin = {"live": bool(inputs.get("live")), "config_path": inputs.get("config_path"), **begin}
        repair = up.get("run_pr_repair_department") or {}
        selected_repair = up.get("select_pr_repair_department") or {}
        if selected_repair.get("route") == "fail_closed":
            # Authorization failure skips the child; its condition_not_met
            # placeholder must not erase the selector's named blocker.
            repair = selected_repair
        elif repair.get("repair"):
            # Carry the authorized start identity even when the child fails
            # before its domain summary. Never replace the child's new head.
            repair = {
                **{key: selected_repair[key] for key in (
                    "repo", "pr", "branch", "repair_kind",
                    "repair_start_head_sha", "reviewed_head_sha",
                ) if key in selected_repair},
                **repair,
            }
        out = record_pass.record(
            pass_dir=str(begin.get("pass_dir") or ""),
            begin=begin,
            prs=up.get("run_pr_triage_department") or {},
            repair=repair,
            issues=up.get("run_executor_department")
            or up.get("run_issue_triage_department")
            or {},
            leftover=up.get("leftover_catalog") or up.get("leftover") or {},
            host_gate=gate,
        )
        return out

    if atom == "compact_state":
        return _run_atom_main(compact_state.main, [*cfg])

    return None
