"""Fala bindings for the prs parent: sieve, optional repair, receipt."""

from typing import Any


def handle_prs(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "list_open_prs":
        from lokay.proc.list_open_prs import run

        return run(config_path=config, live=live)
    if atom == "select_next_pr":
        from lokay.proc.select_next_pr import select

        return select(up.get("list_open_prs") or {})
    if atom == "run_pr_triage_subflow":
        from lokay.proc.run_pr_triage_subflow import run

        return run(up.get("select_next_pr") or {}, config_path=config, live=live)
    if atom == "select_pr_repair":
        from lokay.config import load_config
        from lokay.proc.select_pr_repair import select

        cfg = load_config(config)
        return select(
            up.get("select_next_pr") or {},
            up.get("run_pr_triage_subflow") or {},
            enabled=bool(cfg.executor_enabled and cfg.max_repairs_per_tick > 0),
        )
    if atom == "run_pr_repair_subflow":
        from lokay.proc.run_parent_pr_repair_subflow import run

        return run(up.get("select_pr_repair") or {}, config_path=config, live=live)
    if atom == "summarize_prs":
        from lokay.proc.summarize_prs import summarize

        return summarize(
            up.get("select_next_pr") or {},
            up.get("run_pr_triage_subflow") or {},
            up.get("select_pr_repair") or {},
            up.get("run_pr_repair_subflow") or {},
        )
    return None
