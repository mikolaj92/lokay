"""Experiment: self_repair body is one agent call. Child Fala stays unused."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.agent import AgentError, run_agent
from lokay.config import load_config
from lokay.pr_review import PrReviewError, extract_json_object
from lokay.proc._common import runner
from lokay.tool_contracts import render_contract


def run(*, config_path: str | None = None) -> dict:
    cfg = load_config(config_path)
    prompt = render_contract(
        "department_self_repair",
        context=json.dumps({"config_path": config_path}, ensure_ascii=False, default=str),
    )
    worktree = Path(__file__).resolve().parents[3]
    try:
        result = run_agent(
            runner(cfg),
            cfg,
            worktree=worktree,
            prompt=prompt,
            execute=True,
            session_kind="department-self-repair",
            timeout_seconds=int(cfg.timeout_seconds),
            attach_collector_boundary=True,
        )
    except AgentError as exc:
        return {"ok": False, "department": "self_repair", "error": str(exc), "body": "agent"}
    if result.get("timed_out") or result.get("status") != "completed":
        return {
            "ok": False,
            "department": "self_repair",
            "error": "agent_did_not_complete",
            "status": result.get("status"),
            "timed_out": bool(result.get("timed_out")),
            "body": "agent",
        }
    try:
        parsed = extract_json_object(str(result.get("stdout_tail") or ""))
    except PrReviewError as exc:
        return {"ok": False, "department": "self_repair", "error": str(exc), "body": "agent"}
    parsed["body"] = "agent"
    return parsed
