"""Parent slot: PR sieve only. Does not call pr_repair from inside."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.proc.department_agent_runtime import (
    execute_department_agent,
    load_department_cfg,
    prompt_for,
)


def child_graph(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="pr_triage_department",
        repo="local/pr-triage-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    cfg = load_department_cfg(config_path)

    def child_body() -> dict:
        return child_graph(pass_dir=pass_dir, config_path=config_path, live=live)

    if cfg is None:
        return {**child_body(), "body": "child"}
    return execute_department_agent(
        "pr_triage",
        cfg=cfg,
        live=live,
        prompt=prompt_for(
            "pr_triage",
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
            merge_enabled=bool(cfg.merge_enabled),
            require_checks=bool(cfg.require_checks),
            require_llm_review=bool(cfg.require_llm_review),
            branch_prefix=str(cfg.branch_prefix),
        ),
        child=child_body,
        pass_dir=pass_dir,
    )
