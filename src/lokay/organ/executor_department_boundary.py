"""Fala bindings for the executor department (code and PR, not sieve)."""

from typing import Any


def _listed_of(inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    listed = up.get("list_open_issues") or inputs.get("listed") or {}
    return listed if isinstance(listed, dict) else {}


def _last_of(inputs: dict[str, Any]) -> dict[str, Any]:
    last = inputs.get("last") or {}
    return last if isinstance(last, dict) else {}


def handle_executor_department(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "select_issue_do_row":
        from lokay.proc.select_issue_do_row import pick, select

        picked = up.get("select_next_issue") or pick(
            _listed_of(inputs, up), _last_of(inputs)
        )
        return select(picked, _listed_of(inputs, up))
    if atom == "run_executor_rows":
        from lokay.proc.run_executor_rows import run

        budget = inputs.get("issue_budget")
        return run(
            listed=_listed_of(inputs, up),
            config_path=config,
            live=live,
            pass_dir=pass_dir,
            budget=int(budget) if budget is not None else None,
            last=_last_of(inputs),
        )
    if atom == "summarize_executor_row":
        from lokay.proc.summarize_executor_row import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_executor") or up.get("select_issue_do_row") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=pass_dir,
        )
    if atom == "summarize_executor_department":
        from lokay.proc.summarize_executor_department import summarize

        return summarize(up.get("run_executor_rows") or {})
    return None
