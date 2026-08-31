"""Run the one PR-repair pass after a closed evidence supplement."""

import json
from lokay.proc.run_coding_retry_agent import run
from lokay.tool_contracts import render_contract


def execute(*, cfg, worktree, evidence: dict, live: bool) -> dict:
    prompt = render_contract(
        "evidence_repair",
        evidence=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
    )
    return run(cfg=cfg, worktree=worktree, prompt=prompt, live=live)
