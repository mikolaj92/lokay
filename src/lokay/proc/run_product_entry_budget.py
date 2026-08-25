"""Run exactly one existing authored product pass-budget subflow."""

from lokay.proc.product_pass_budget_subflow import run


def execute(*, config_path: str | None, live: bool, max_passes: int) -> dict:
    return {
        "ok": True,
        "route": "terminal",
        "payload": run(config_path=config_path, live=live, max_passes=max_passes),
    }
