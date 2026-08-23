"""Execute one read-only issue-triage prompt through the configured agent."""

from __future__ import annotations
from pathlib import Path
from lokay.agent import run_agent
from lokay.proc._common import agent_execute_allowed, runner


def execute(*, cfg, repo: str, issue: int, clone_path, prompt: str, live: bool) -> dict:
    allowed = agent_execute_allowed(cfg, live_flag=live)
    worktree = (
        Path(clone_path) if clone_path and Path(clone_path).is_dir() else Path.cwd()
    )
    result = run_agent(
        runner(cfg),
        cfg,
        worktree=worktree,
        prompt=prompt,
        execute=allowed and live,
        session_kind="intake",
        timeout_seconds=180,
        attach_collector_boundary=False,
    )
    if result.get("status") != "completed":
        return {
            "ok": True,
            "route": "failed",
            "status": str(result.get("status") or "failed"),
            "stdout": "",
        }
    return {
        "ok": True,
        "route": "completed",
        "repo": repo,
        "issue": issue,
        "stdout": str(result.get("stdout_tail") or ""),
        "agent": result,
    }
