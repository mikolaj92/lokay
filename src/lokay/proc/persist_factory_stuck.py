"""Persist one harvested factory stuck ledger."""

from pathlib import Path
from lokay.stuck import save_stuck


def persist(ledger: dict, harvested: dict) -> dict:
    save_stuck(Path(ledger["stuck_path"]), dict(harvested["stuck"]))
    return {"ok": True, "stuck_path": ledger["stuck_path"], "stuck": harvested["stuck"]}
