"""Prepare bounded catalog, scope, and TTL facts for PR survey."""

from lokay.factory_scope import factory_repo, scoped_repos
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working
from lokay.proc.survey_ttl import survey_recently_empty, survey_stamp_path


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin, _ = load_begin_working(pass_dir)
    repos = list(begin.get("repos") or [])
    if len(repos) > slot_count:
        return {
            "ok": False,
            "error": "PR survey catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": slot_count,
        }
    scope = survey_scope(begin)
    _, skipped = scoped_repos(repos, lokay=factory_repo())
    return {
        "ok": True,
        "repos": repos,
        "mini_repo": factory_repo(),
        "skipped_repos": skipped,
        "active_repos": sorted(scope) if scope is not None else repos,
        "scoped": scope is not None,
        "recent_empty": survey_recently_empty(survey_stamp_path(begin)),
    }
