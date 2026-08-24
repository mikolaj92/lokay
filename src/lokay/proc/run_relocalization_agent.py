"""Run exactly one off-goal relocalization agent attempt."""

from pathlib import Path

from lokay.agent import run_agent
from lokay.proc._common import runner


def run(evidence: dict, request: dict, *, config: object, feedback: str = "") -> dict:
    try:
        out = run_agent(
            runner(config),
            config,
            worktree=Path(evidence["worktree"]),
            prompt=request["prompt"] + feedback,
            execute=True,
            session_kind="localize",
            timeout_seconds=180,
            attach_collector_boundary=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "executor_failed",
            "error": str(exc),
        }
    status = str(out.get("status") or "")
    return {
        "ok": True,
        "route": "validate" if status == "completed" else "terminal",
        "reason": "timeout" if status == "timeout" else "executor_failed",
        "text": str(out.get("stdout_tail") or ""),
    }
