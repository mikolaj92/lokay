"""Fala bindings for issue Unix atoms used by the department waves."""

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
    if atom == "list_open_issues":
        from lokay.proc.list_open_issues import run

        return run(config_path=config, live=live)
    if atom == "select_next_issue":
        from lokay.proc.select_next_issue import select

        return select(_listed_of(inputs, up), _last_of(inputs))
    if atom == "issues_run_triage":
        from lokay.proc.run_issue_triage_subflow import run

        return run(up.get("select_next_issue") or {}, config_path=config)
    if atom == "select_issue_executor":
        from lokay.config import department_enabled, load_config
        from lokay.proc.select_issue_executor import select

        cfg = load_config(config)
        return select(
            up.get("select_issue_do_row") or {},
            enabled=department_enabled(cfg, "executor"),
        )
    if atom == "issues_launch_pr":
        from lokay.proc.launch_issue_to_pr import launch

        return launch(
            up.get("select_issue_executor") or {},
            config_path=config,
        )
    return None
