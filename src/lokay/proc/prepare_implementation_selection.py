"""Prepare bounded inputs for implementation-repository selection."""

from pathlib import Path
from lokay.passkit import io as pass_io
from lokay.stuck import load_stuck
from lokay.mill_scope import mill_repo, scoped_repos


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    repos = list(begin.get("repos") or [])
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "implementation catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    path = str(begin.get("stuck_path") or "")
    if path and Path(path).is_file():
        stuck = load_stuck(Path(path))
    _, skipped = scoped_repos(repos, mill=mill_repo())
    active = bool(begin.get("live")) and int(begin.get("issue_budget") or 0) > 0
    return {
        "ok": True,
        "route": "select" if active else "no_budget",
        "repos": repos if active else [],
        "issue_budget": int(begin.get("issue_budget") or 0),
        "executor_enabled": bool(begin.get("executor_enabled")),
        "skipped_repos": skipped,
        "stuck": stuck,
    }
