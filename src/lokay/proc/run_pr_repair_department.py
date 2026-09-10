"""Parent slot: existing pr_repair child when the factory select routes repair."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc.department_agent_runtime import (
    execute_department_agent,
    load_department_cfg,
    prompt_for,
)
from lokay.proc.run_parent_pr_repair_subflow import run as run_repair


def mill(selected: Mapping[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
    route = str(selected.get("route") or "")
    if route == "fail_closed":
        return ok(
            route="fail_closed",
            reason=str(selected.get("reason") or "pr_repair_budget_exhausted"),
            parked=True,
            repairable=True,
            attempts=int(selected.get("attempts") or 0),
            budget=max(1, int(selected.get("budget") or 1)),
            repo=str(selected.get("repo") or ""),
            pr=int(selected.get("pr") or 0),
            branch=str(selected.get("branch") or ""),
        )
    if route != "repair":
        return ok(route="skip", reason=str(selected.get("reason") or "not_selected"))
    return run_repair(selected, config_path=config_path, live=live)


def run(
    selected: Mapping[str, Any],
    *,
    config_path: str | None,
    live: bool,
) -> dict[str, Any]:
    def mill_body() -> dict[str, Any]:
        return mill(selected, config_path=config_path, live=live)

    route = str(selected.get("route") or "")
    if route in {"fail_closed", ""} or route != "repair":
        return {**mill_body(), "body": "mill"}
    cfg = load_department_cfg(config_path)
    if cfg is None:
        return {**mill_body(), "body": "mill"}
    return execute_department_agent(
        "pr_repair",
        cfg=cfg,
        live=live,
        prompt=prompt_for("pr_repair", selected=dict(selected), live=live),
        mill=mill_body,
    )
