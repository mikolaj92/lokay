"""Persist the pass stuck ledger after one dispatch outcome."""

from pathlib import Path
from lokay.passkit import io as pass_io
from lokay.stuck import save_stuck


def apply(*, pass_dir: str) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    save_stuck(
        Path(str(begin.get("stuck_path") or "")), dict(working.get("stuck") or {})
    )
    return {"ok": True, "applied": True}
