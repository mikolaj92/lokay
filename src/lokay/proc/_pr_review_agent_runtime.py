"""Shared physical execution for one read-only PR-review prompt."""
from __future__ import annotations
from lokay.agent import run_agent
from lokay.envelope import err, ok
from lokay.pr_review_io import review_worktree
from lokay.proc._common import agent_execute_allowed, runner

def execute(*, cfg, repo: str, pr: int, head_sha: str, prompt: str, live: bool) -> dict:
    allowed=agent_execute_allowed(cfg,live_flag=live)
    result=run_agent(runner(cfg),cfg,worktree=review_worktree(cfg,repo),prompt=prompt,execute=allowed and live)
    if result.get("status") == "failed":
        return err("pr_review agent failed",agent=result)
    return ok(repo=repo,pr=pr,head_sha=head_sha,agent=result,stdout=str(result.get("stdout_tail") or ""))
