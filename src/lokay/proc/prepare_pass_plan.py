"""Prepare bounded pass-planning inputs and durable stuck state."""

from pathlib import Path
from lokay.passkit import io as pass_io
from lokay.stuck import load_stuck
from lokay.factory_scope import factory_repo, scoped_repos


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    repos = list(begin.get("repos") or [])
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "planning catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    path = str(begin.get("stuck_path") or "")
    stuck = load_stuck(Path(path)) if path else dict(begin.get("stuck") or {})
    _, skipped = scoped_repos(repos, lokay=factory_repo())
    return {
        "ok": True,
        "repos": repos,
        "live": bool(begin.get("live")),
        "triage_budget": int(begin.get("triage_budget") or 0),
        "stuck": stuck,
        "skipped_repos": skipped,
    }
