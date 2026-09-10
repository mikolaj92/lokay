"""High-entropy department body: one agent slot, authored child as fallback.

The parent Fala graph and department child paths stay. This runtime only
replaces the department body. Invalid or refused agent output falls back to
the authored child Fala.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from lokay.agent import run_agent
from lokay.config import Config, department_enabled, load_config
from lokay.pr_review import PrReviewError, extract_json_object
from lokay.proc._common import agent_execute_allowed, runner, semantic_agent_allowed
from lokay.tool_contracts import render_contract

ChildGraph = Callable[[], dict[str, Any]]

DEPARTMENTS = (
    "self_repair",
    "issue_triage",
    "executor",
    "pr_triage",
    "pr_repair",
)

_REQUIRED = {
    "self_repair": frozenset({"ok", "department", "route"}),
    "issue_triage": frozenset({"ok", "department", "route", "launched"}),
    "executor": frozenset({"ok", "department", "route", "merged"}),
    "pr_triage": frozenset({"ok", "department", "route", "verdict", "repair_started"}),
    "pr_repair": frozenset({"ok", "route"}),
}

_CODING = frozenset({"executor", "pr_repair", "self_repair"})


def agent_bodies_enabled(cfg: Config | None) -> bool:
    if cfg is None:
        return True
    return bool(getattr(cfg, "department_agent_bodies", True))


def load_department_cfg(config_path: str | None) -> Config | None:
    if not config_path:
        return None
    try:
        return load_config(config_path)
    except FileNotFoundError:
        return None


def worktree_for(cfg: Config | None, *, pass_dir: str = "") -> Path:
    if pass_dir:
        path = Path(pass_dir).expanduser()
        if path.is_dir():
            return path
    if cfg is not None:
        for repo in cfg.active_repos():
            if repo.clone_path.is_dir():
                return repo.clone_path
    root = Path(__file__).resolve().parents[3]
    return root if (root / "pyproject.toml").is_file() else Path.cwd()


def _context_blob(values: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in values.items() if value is not None}
    return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)[:24000]


def prompt_for(department: str, **values: Any) -> str:
    return render_contract(f"department_{department}", context=_context_blob(values))


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def normalize(department: str, payload: Mapping[str, Any]) -> dict[str, Any] | None:
    data = _as_dict(payload)
    if data.get("ok") is not True:
        return None
    if str(data.get("route") or "") == "child":
        return None
    required = _REQUIRED[department]
    missing = [key for key in required if key not in data]
    if missing:
        return None
    if department != "pr_repair" and str(data.get("department") or "") != department:
        return None
    if department == "issue_triage":
        data["launched"] = None
        result = _as_dict(data.get("result"))
        data["result"] = {
            **result,
            "launched": None,
            "department": "issue_triage",
        }
        data["department"] = "issue_triage"
    elif department == "executor":
        data["merged"] = False
        result = _as_dict(data.get("result"))
        data["result"] = {**result, "merged": False, "department": "executor"}
        data["department"] = "executor"
    elif department == "pr_triage":
        data["repair_started"] = False
        receipt = {
            "ok": True,
            "department": "pr_triage",
            "route": str(data.get("route") or "none"),
            "verdict": str(data.get("verdict") or "none"),
            "repo": data.get("repo"),
            "pr": data.get("pr"),
            "branch": data.get("branch"),
            "triage": _as_dict(data.get("triage")),
            "repair_started": False,
            "trace": data.get("trace"),
        }
        nested = {**receipt, **_as_dict(data.get("result")), "repair_started": False}
        data = {**receipt, "result": nested}
    elif department == "self_repair":
        data["department"] = "self_repair"
    if not str(data.get("trace") or "").strip():
        return None
    data["body"] = "agent"
    return data


def execute_department_agent(
    department: str,
    *,
    cfg: Config,
    live: bool,
    prompt: str,
    child: ChildGraph,
    pass_dir: str = "",
    timeout_seconds: int | None = None,
    require_healthy: bool = True,
) -> dict[str, Any]:
    """Run one department agent. Authored child on refuse, timeout, or invalid JSON."""
    if not agent_bodies_enabled(cfg) or not department_enabled(cfg, department):
        return {**child(), "body": "child"}
    allowed = (
        agent_execute_allowed(cfg, live_flag=live)
        if require_healthy
        else semantic_agent_allowed(cfg, live_flag=live)
    )
    if not allowed:
        return {**child(), "body": "child"}
    worktree = worktree_for(cfg, pass_dir=pass_dir)
    timeout = timeout_seconds if timeout_seconds is not None else int(cfg.timeout_seconds)
    result = run_agent(
        runner(cfg),
        cfg,
        worktree=worktree,
        prompt=prompt,
        execute=True,
        session_kind=f"department-{department.replace('_', '-')}",
        timeout_seconds=timeout,
        attach_collector_boundary=department in _CODING,
    )
    if result.get("timed_out") or result.get("status") != "completed":
        child_out = child()
        return {
            **child_out,
            "body": "child",
            "agent_status": str(result.get("status") or "failed"),
            "agent_timed_out": bool(result.get("timed_out")),
        }
    try:
        parsed = extract_json_object(str(result.get("stdout_tail") or ""))
    except PrReviewError:
        child_out = child()
        return {
            **child_out,
            "body": "child",
            "agent_status": "invalid_json",
        }
    normalized = normalize(department, parsed)
    if normalized is None:
        child_out = child()
        return {
            **child_out,
            "body": "child",
            "agent_status": "invalid_contract",
        }
    normalized["agent"] = {
        "status": result.get("status"),
        "session": result.get("session"),
        "returncode": result.get("returncode"),
    }
    return normalized

