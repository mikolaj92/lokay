"""Run the single coding-agent retry after invalid JSON."""

from __future__ import annotations
from lokay.agent import run_agent
from lokay.proc._common import agent_execute_allowed, runner


def run(*, cfg, worktree, prompt: str, live: bool) -> dict:
    result = run_agent(
        runner(cfg),
        cfg,
        worktree=worktree,
        prompt=prompt,
        execute=agent_execute_allowed(cfg, live_flag=live) and live,
        session_kind="code",
        attach_collector_boundary=False,
    )
    return {
        "ok": True,
        "route": "completed" if result.get("status") == "completed" else "failed",
        "stdout": str(result.get("stdout_tail") or ""),
        "agent": result,
    }
