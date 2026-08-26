"""Fala bindings for the PRs child: scope, list, filter, recenzja, merge."""

from typing import Any


def handle_prs(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "read_prs_scope":
        from lokay.proc.read_prs_scope import read

        return read(config_path=config)
    if atom == "list_open_prs":
        from lokay.proc.list_open_prs import run

        return run(up.get("read_prs_scope") or {}, live=live)
    if atom == "filter_mill_prs":
        from lokay.proc.filter_mill_prs import filter_rows

        return filter_rows(
            up.get("list_open_prs") or {},
            up.get("read_prs_scope") or {},
        )
    if atom == "select_next_pr":
        from lokay.proc.select_next_pr import select

        return select(up.get("filter_mill_prs") or {})
    if atom == "prs_run_triage":
        from lokay.proc.run_pr_triage_subflow import run

        return run(up.get("select_next_pr") or {}, config_path=config, live=live)
    if atom == "summarize_prs":
        from lokay.proc.summarize_prs import summarize

        return summarize(
            up.get("select_next_pr") or {},
            up.get("prs_run_triage") or {},
        )
    return None
