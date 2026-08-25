"""Read one factory stuck ledger."""

from pathlib import Path
from lokay.stuck import load_stuck, stuck_path_for


def read(config: dict) -> dict:
    path = stuck_path_for(Path(config["state_path"]))
    stuck = load_stuck(path)
    issues = stuck.get("issues") or {}
    return {
        "ok": True,
        "stuck_path": str(path),
        "issue_count": len(issues) if isinstance(issues, dict) else 0,
    }
