"""Parent slot: executor_department. Code and PR. Not sieve. Not merge."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.proc.department_agent_runtime import (
    execute_department_agent,
    load_department_cfg,
    prompt_for,
)


def child_graph(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage: dict | None = None,
) -> dict:
    return run_path(
        path_id="executor_department",
        repo="local/executor-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir, "triage": triage or {}},
    )


def run(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage_ran: bool = False,
    triage: dict | None = None,
) -> dict:
    del triage_ran  # sieve is a sibling department; this slot always codes
    cfg = load_department_cfg(config_path)

    def child_body() -> dict:
        return child_graph(
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
            triage=triage,
        )

    if cfg is None:
        return {**child_body(), "body": "child"}
    return execute_department_agent(
        "executor",
        cfg=cfg,
        live=live,
        prompt=prompt_for(
            "executor",
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
            triage=triage or {},
        ),
        child=child_body,
        pass_dir=pass_dir,
    )
