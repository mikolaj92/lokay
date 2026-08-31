"""Run one bounded repair pass from a red PR local-test log."""

from lokay.proc.run_coding_retry_agent import run
from lokay.tool_contracts import render_contract


def execute(*, cfg, worktree, test: dict, live: bool) -> dict:
    log = "\n".join(
        x
        for x in (
            str(test.get("stdout_tail") or ""),
            str(test.get("stderr_tail") or ""),
            str(test.get("error") or ""),
        )
        if x.strip()
    )
    prompt = render_contract("pr_test_repair", test_log=log[-6000:])
    return run(cfg=cfg, worktree=worktree, prompt=prompt, live=live)
