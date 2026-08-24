"""Run exactly one localization agent attempt and return transport facts."""

from pathlib import Path

from lokay.agent import run_agent
from lokay.proc._common import runner


def run(
    request: dict, agent_request: dict, *, config: object, prompt_suffix: str = ""
) -> dict:
    try:
        out = run_agent(
            runner(config),
            config,
            worktree=Path(request["worktree"]),
            prompt=agent_request["prompt"] + prompt_suffix,
            execute=True,
            session_kind="localize",
            timeout_seconds=180,
            attach_collector_boundary=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "fallback",
            "status": "executor_failed",
            "error": str(exc),
        }
    status = str(out.get("status") or "")
    return {
        "ok": True,
        "route": "validate" if status == "completed" else "fallback",
        "status": status,
        "text": str(out.get("stdout_tail") or ""),
    }
