"""Parent slot: PR sieve only. Does not call pr_repair from inside."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.proc.department_agent_runtime import (
    execute_department_agent,
    load_department_cfg,
    prompt_for,
)


def mill(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="pr_triage_department",
        repo="local/pr-triage-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    cfg = load_department_cfg(config_path)

    def mill_body() -> dict:
        return mill(pass_dir=pass_dir, config_path=config_path, live=live)

    if cfg is None:
        return {**mill_body(), "body": "mill"}
    return execute_department_agent(
        "pr_triage",
        cfg=cfg,
        live=live,
        prompt=prompt_for(
            "pr_triage",
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
        ),
        mill=mill_body,
        pass_dir=pass_dir,
    )
