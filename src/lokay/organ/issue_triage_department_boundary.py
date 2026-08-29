"""Fala bindings for the issue_triage department (sieve + split + intake)."""

from typing import Any


def _listed_of(inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    listed = up.get("list_open_issues") or inputs.get("listed") or {}
    return listed if isinstance(listed, dict) else {}


def _last_of(inputs: dict[str, Any]) -> dict[str, Any]:
    last = inputs.get("last") or {}
    return last if isinstance(last, dict) else {}


def handle_issue_triage_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "run_issue_sieve_rows":
        from lokay.proc.run_issue_sieve_rows import run

        return run(
            listed=_listed_of(inputs, up),
            config_path=config,
            live=live,
            pass_dir=pass_dir,
            last=_last_of(inputs),
        )
    if atom == "select_issue_sieve":
        from lokay.proc.select_issue_sieve import select

        return select(
            up.get("select_next_issue") or {},
            up.get("issues_run_triage") or {},
            _listed_of(inputs, up),
        )
    if atom == "run_issue_sieve_split":
        from lokay.proc.run_issue_sieve_split import run

        return run(up.get("select_issue_sieve") or {}, config_path=config, live=live)
    if atom == "run_issue_sieve_intake":
        from lokay.proc.run_issue_sieve_intake import run

        return run(up.get("select_issue_sieve") or {}, config_path=config, live=live)
    if atom == "summarize_issue_sieve_row":
        from lokay.proc.summarize_issue_sieve_row import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_sieve") or {},
            up.get("run_issue_sieve_split") or {},
            up.get("run_issue_sieve_intake") or {},
        )
    if atom == "summarize_issue_triage_department":
        from lokay.proc.summarize_issue_triage_department import summarize

        return summarize(up.get("run_issue_sieve_rows") or {})
    return None
