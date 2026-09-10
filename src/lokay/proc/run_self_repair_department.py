"""Parent slot: child Fala self_repair_department (incident + existing self_repair)."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.proc.department_agent_runtime import (
    execute_department_agent,
    load_department_cfg,
    prompt_for,
)


def mill(*, config_path: str | None) -> dict:
    return run_path(
        path_id="self_repair_department",
        repo="__self_repair_department__",
        config_path=config_path,
        live=True,
        require_healthy=False,
        extra_inputs={"config_path": config_path or ""},
    )


def run(*, config_path: str | None = None) -> dict:
    cfg = load_department_cfg(config_path)

    def mill_body() -> dict:
        return mill(config_path=config_path)

    if cfg is None:
        return {**mill_body(), "body": "mill"}
    live = bool(cfg.live and cfg.executor_enabled)
    return execute_department_agent(
        "self_repair",
        cfg=cfg,
        live=live,
        prompt=prompt_for("self_repair", config_path=config_path),
        mill=mill_body,
        require_healthy=False,
    )
