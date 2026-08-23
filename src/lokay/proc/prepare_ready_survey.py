"""Prepare the bounded catalog and TTL route for ready survey."""

from lokay.mill_scope import mill_repo, scoped_repos
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working
from lokay.proc.survey_ttl import survey_recently_empty, survey_stamp_path


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin, _ = load_begin_working(pass_dir)
    repos, skipped = scoped_repos(list(begin.get("repos") or []), mill=mill_repo())
    active = set(survey_scope(begin) or repos)
    slots = [] if survey_recently_empty(survey_stamp_path(begin)) else list(repos)
    if len(slots) > slot_count:
        return {
            "ok": False,
            "error": "ready survey catalog exceeds authored slots",
            "count": len(slots),
            "slot_count": slot_count,
        }
    return {
        "ok": True,
        "route": "skip" if not slots else "survey",
        "repos": slots,
        "active_repos": sorted(active),
        "skipped_repos": list(skipped),
        "recent_empty": not slots,
    }
