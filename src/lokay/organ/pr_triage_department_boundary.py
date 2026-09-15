"""Fala bindings for the pr_triage department (PR sieve, not repair)."""

from typing import Any


def handle_pr_triage_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "list_pr_sieve":
        from lokay.proc.list_open_prs import run

        return run(config_path=config, live=live)
    if atom == "select_pr_sieve":
        from lokay.proc.select_next_pr import select

        return select(up.get("list_pr_sieve") or {})
    if atom == "reconcile_pr_repair_push":
        from lokay.proc.reconcile_pr_repair_push import reconcile_pending

        picked = dict(up.get("select_pr_sieve") or {})
        return reconcile_pending(config_path=config, live=live, selection=picked)
    if atom == "run_pr_sieve":
        from lokay.proc.run_pr_triage_subflow import run

        return run(up.get("select_pr_sieve") or {}, config_path=config, live=live)
    if atom == "select_pr_triage_verdict":
        from lokay.proc.select_pr_triage_verdict import select

        return select(
            up.get("select_pr_sieve") or {},
            up.get("run_pr_sieve") or {},
            up.get("reconcile_pr_repair_push") or {},
        )
    if atom == "summarize_pr_triage_department":
        from lokay.proc.summarize_pr_triage_department import summarize

        return summarize(
            up.get("select_pr_sieve") or {},
            up.get("run_pr_sieve") or {},
            up.get("select_pr_triage_verdict") or {},
            up.get("reconcile_pr_repair_push") or {},
        )
    return None
