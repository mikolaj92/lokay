"""Read one factory stuck ledger."""

from pathlib import Path
from lokay.stuck import load_stuck, stuck_path_for


def read(config: dict) -> dict:
    path = stuck_path_for(Path(config["state_path"]))
    return {"ok": True, "stuck_path": str(path), "stuck": load_stuck(path)}
