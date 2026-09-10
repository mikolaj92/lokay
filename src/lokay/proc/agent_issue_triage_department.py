"""Experiment: issue_triage body is one agent call. Child Fala stays unused."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.agent import AgentError, run_agent
from lokay.config import load_config
from lokay.pr_review import PrReviewError, extract_json_object
from lokay.proc._common import runner
from lokay.tool_contracts import render_contract


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    cfg = load_config(config_path)
    prompt = render_contract(
        "department_issue_triage",
        context=json.dumps(
            {"pass_dir": pass_dir, "config_path": config_path, "live": live},
            ensure_ascii=False,
            default=str,
        ),
    )
    worktree = Path(pass_dir).expanduser() if pass_dir else Path(__file__).resolve().parents[3]
    if not worktree.is_dir():
        worktree = Path(__file__).resolve().parents[3]
    try:
        result = run_agent(
            runner(cfg),
            cfg,
            worktree=worktree,
            prompt=prompt,
            execute=True,
            session_kind="department-issue-triage",
            timeout_seconds=int(cfg.timeout_seconds),
            attach_collector_boundary=False,
        )
    except AgentError as exc:
        return {"ok": False, "department": "issue_triage", "error": str(exc), "body": "agent", "launched": None}
    if result.get("timed_out") or result.get("status") != "completed":
        return {
            "ok": False,
            "department": "issue_triage",
            "error": "agent_did_not_complete",
            "status": result.get("status"),
            "timed_out": bool(result.get("timed_out")),
            "body": "agent",
            "launched": None,
        }
    try:
        parsed = extract_json_object(str(result.get("stdout_tail") or ""))
    except PrReviewError as exc:
        return {"ok": False, "department": "issue_triage", "error": str(exc), "body": "agent", "launched": None}
    parsed["body"] = "agent"
    parsed["launched"] = None
    return parsed
