"""Parent slot: existing pr_repair child when the factory select routes repair."""

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc.run_parent_pr_repair_subflow import run as run_repair


def run(
    selected: Mapping[str, Any],
    *,
    config_path: str | None,
    live: bool,
) -> dict[str, Any]:
    if str(selected.get("route") or "") != "repair":
        return ok(route="skip", reason=str(selected.get("reason") or "not_selected"))
    return run_repair(selected, config_path=config_path, live=live)
