"""Experiment: pr_repair body is one agent call. Child Fala stays unused."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from lokay.agent import AgentError, run_agent
from lokay.config import load_config
from lokay.pr_review import PrReviewError, extract_json_object
from lokay.proc._common import runner
from lokay.tool_contracts import render_contract


def run(selected: Mapping[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
    cfg = load_config(config_path)
    prompt = render_contract(
        "department_pr_repair",
        context=json.dumps(
            {"selected": dict(selected), "config_path": config_path, "live": live},
            ensure_ascii=False,
            default=str,
        ),
    )
    worktree = Path(__file__).resolve().parents[3]
    try:
        result = run_agent(
            runner(cfg),
            cfg,
            worktree=worktree,
            prompt=prompt,
            execute=True,
            session_kind="department-pr-repair",
            timeout_seconds=int(cfg.timeout_seconds),
            attach_collector_boundary=True,
        )
    except AgentError as exc:
        return {"ok": False, "error": str(exc), "body": "agent"}
    if result.get("timed_out") or result.get("status") != "completed":
        return {
            "ok": False,
            "error": "agent_did_not_complete",
            "status": result.get("status"),
            "timed_out": bool(result.get("timed_out")),
            "body": "agent",
        }
    try:
        parsed = extract_json_object(str(result.get("stdout_tail") or ""))
    except PrReviewError as exc:
        return {"ok": False, "error": str(exc), "body": "agent"}
    parsed["body"] = "agent"
    return parsed
