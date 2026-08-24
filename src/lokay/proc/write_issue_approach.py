"""Write exactly one prepared deterministic approach file."""

from pathlib import Path

from lokay.approach_plan import write_approach_file


def write(request: dict, approach: dict) -> dict:
    try:
        path = write_approach_file(
            Path(request["worktree"]), approach["content"], rel_path=request["rel_path"]
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "approach_write_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "written", "path": str(path)}
