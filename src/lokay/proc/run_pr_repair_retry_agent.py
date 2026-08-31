"""Run the single PR-repair agent retry after invalid JSON."""

from lokay.proc.run_coding_retry_agent import run
from lokay.tool_contracts import render_contract


def execute(*, cfg, worktree, error: str, stdout: str, live: bool) -> dict:
    prompt = render_contract(
        "pr_repair_retry", error=error, stdout=stdout[-2000:]
    )
    return run(cfg=cfg, worktree=worktree, prompt=prompt, live=live)
