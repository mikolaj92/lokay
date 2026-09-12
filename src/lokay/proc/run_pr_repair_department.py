"""Parent slot: existing pr_repair child when the factory select routes repair."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc.run_parent_pr_repair_subflow import run as run_repair


def child_graph(selected: Mapping[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
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
    def child_body() -> dict[str, Any]:
        return child_graph(selected, config_path=config_path, live=live)

    return {**child_body(), "body": "child"}
