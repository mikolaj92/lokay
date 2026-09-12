"""Parent slot: child Fala self_repair_department (incident + existing self_repair)."""

from __future__ import annotations

from lokay.graph_run import run_path


def child_graph(*, config_path: str | None) -> dict:
    return run_path(
        path_id="self_repair_department",
        repo="__self_repair_department__",
        config_path=config_path,
        live=True,
        require_healthy=False,
        extra_inputs={"config_path": config_path or ""},
    )


def run(*, config_path: str | None = None) -> dict:
    return {**child_graph(config_path=config_path), "body": "child"}
