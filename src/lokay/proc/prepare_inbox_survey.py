"""Prepare bounded catalog, scope, ledger, and TTL facts for inbox survey."""

from pathlib import Path
from lokay.factory_scope import factory_repo, scoped_repos
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working
from lokay.proc.survey_ttl import survey_recently_empty, survey_stamp_path
from lokay.stuck import load_stuck


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin, working = load_begin_working(pass_dir)
    repos = list(begin.get("repos") or [])
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "inbox survey catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    _, skipped = scoped_repos(repos, lokay=factory_repo())
    scope = survey_scope(begin)
    path = str(begin.get("stuck_path") or "")
    stuck = (
        load_stuck(Path(path))
        if path
        else dict(working.get("stuck") or begin.get("stuck") or {})
    )
    recent = survey_recently_empty(survey_stamp_path(begin))
    return {
        "ok": True,
        "repos": repos,
        "mini_repo": factory_repo(),
        "skipped_repos": skipped,
        "active_repos": sorted(scope) if scope is not None else repos,
        "scoped": scope is not None,
        "stuck": stuck,
        "recent_empty": recent,
    }
