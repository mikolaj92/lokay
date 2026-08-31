"""Run one read-only queue-conflict agent call."""

import json
from pathlib import Path
from lokay.agent import run_agent
from lokay.proc._common import runner, semantic_agent_allowed
from lokay.tool_contracts import render_contract


def prompt(target: dict) -> str:
    evidence = {
        "candidate": target.get("candidate"),
        "open_prs": list(target.get("open_prs") or [])[:12],
        "peer_issues": list(target.get("peer_issues") or [])[:12],
    }
    return render_contract(
        "queue_conflict_process",
        evidence=json.dumps(evidence, ensure_ascii=False),
    )


def run(*, cfg, target: dict, live: bool, retry_feedback: dict | None = None) -> dict:
    text = prompt(target)
    if retry_feedback:
        from lokay.review_boundary import validation_feedback_prompt

        text += "\n\n" + validation_feedback_prompt(
            str(retry_feedback.get("validation_error") or "invalid output"),
            str(retry_feedback.get("agent_stdout_tail") or ""),
        )
    clone = next(
        (repo.clone_path for repo in cfg.repos if repo.name == target.get("repo")),
        Path.cwd(),
    )
    worktree = Path(clone) if Path(clone).is_dir() else Path.cwd()
    result = run_agent(
        runner(cfg),
        cfg,
        worktree=worktree,
        prompt=text,
        execute=semantic_agent_allowed(cfg, live_flag=live),
        session_kind="queue",
        timeout_seconds=180,
        attach_collector_boundary=False,
    )
    return {
        "ok": True,
        "route": "completed" if result.get("status") == "completed" else "failed",
        "stdout": str(result.get("stdout_tail") or ""),
        "agent": result,
    }
