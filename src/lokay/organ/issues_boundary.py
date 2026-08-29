"""Fala bindings for issues (nest until idle) and one issue_row child."""

from typing import Any


def _listed_of(inputs: dict[str, Any], up: dict[str, dict[str, Any]]) -> dict[str, Any]:
    listed = up.get("list_open_issues") or inputs.get("listed") or {}
    return listed if isinstance(listed, dict) else {}


def _last_of(inputs: dict[str, Any]) -> dict[str, Any]:
    last = inputs.get("last") or {}
    return last if isinstance(last, dict) else {}


def handle_issues(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "list_open_issues":
        from lokay.proc.list_open_issues import run

        return run(config_path=config, live=live)
    if atom == "run_issue_rows":
        from lokay.proc.run_issue_rows import run

        budget = inputs.get("issue_budget")
        return run(
            listed=_listed_of(inputs, up),
            config_path=config,
            live=live,
            pass_dir=pass_dir,
            budget=int(budget) if budget is not None else None,
            last=_last_of(inputs),
        )
    if atom == "select_next_issue":
        from lokay.proc.select_next_issue import select

        return select(_listed_of(inputs, up), _last_of(inputs))
    if atom == "issues_run_triage":
        from lokay.proc.run_issue_triage_subflow import run

        return run(up.get("select_next_issue") or {}, config_path=config)
    if atom == "select_issue_do":
        from lokay.proc.select_issue_do import select

        return select(
            up.get("select_next_issue") or {},
            up.get("issues_run_triage") or {},
            _listed_of(inputs, up),
        )
    if atom == "select_issue_executor":
        from lokay.config import department_enabled, load_config
        from lokay.proc.select_issue_executor import select

        cfg = load_config(config)
        return select(
            up.get("select_issue_do") or {},
            enabled=department_enabled(cfg, "executor"),
        )
    if atom == "issues_launch_pr":
        from lokay.proc.launch_issue_to_pr import launch

        return launch(
            up.get("select_issue_executor") or up.get("select_issue_do") or {},
            config_path=config,
        )
    if atom == "summarize_issue_row":
        from lokay.proc.summarize_issue_row import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_executor") or up.get("select_issue_do") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=pass_dir,
        )
    if atom == "summarize_issues":
        from lokay.proc.summarize_issues import summarize_nest

        nest = up.get("run_issue_rows")
        if nest:
            return summarize_nest(nest, pass_dir=pass_dir)
        from lokay.proc.summarize_issues import summarize

        return summarize(
            up.get("select_next_issue") or {},
            up.get("select_issue_do") or {},
            up.get("issues_launch_pr") or {},
            pass_dir=pass_dir,
        )
    return None
