"""Persist one harvested factory stuck ledger."""

from pathlib import Path
from lokay.stuck import save_stuck


def persist(ledger: dict, harvested: dict) -> dict:
    stuck = dict(harvested["stuck"])
    save_stuck(Path(ledger["stuck_path"]), stuck)
    issues = stuck.get("issues") or {}
    return {
        "ok": True,
        "stuck_path": ledger["stuck_path"],
        "issue_count": len(issues) if isinstance(issues, dict) else 0,
    }
