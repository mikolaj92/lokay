"""Check one triage target against the physical stuck ledger."""

from pathlib import Path
from lokay.passkit import io as pass_io
from lokay.stuck import is_blocked_in_ledger, load_stuck


def check(*, pass_dir: str, target: dict) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    path = str(begin.get("stuck_path") or "")
    stuck = load_stuck(Path(path)) if path else {}
    blocked = is_blocked_in_ledger(stuck, str(target["repo"]), int(target["issue"]))
    return {"ok": True, "route": "blocked" if blocked else "run", **target}
