"""Run the one coding pass after a closed mechanical evidence supplement."""

from __future__ import annotations
import json
from lokay.proc.run_coding_retry_agent import run
from lokay.tool_contracts import render_contract


def execute(*, cfg, worktree, evidence: dict, live: bool) -> dict:
    prompt = render_contract(
        "evidence_coding",
        evidence=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
    )
    return run(cfg=cfg, worktree=worktree, prompt=prompt, live=live)
