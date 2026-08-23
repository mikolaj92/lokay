"""Apply the empty-survey TTL stamp effect."""

from lokay.passkit.working import load_begin_working
from lokay.proc.survey_ttl import (
    clear_survey_stamp,
    survey_stamp_path,
    touch_survey_stamp,
)


def update(*, pass_dir: str, finalized: dict) -> dict:
    begin, working = load_begin_working(pass_dir)
    stamp = survey_stamp_path(begin)
    if stamp and not finalized.get("skipped"):
        nonempty = any(
            int(working.get(key) or 0)
            for key in (
                "remaining_ready",
                "remaining_prs",
                "remaining_inbox",
                "survey_errors",
            )
        ) or bool(finalized.get("probe_failed"))
        clear_survey_stamp(stamp) if nonempty else touch_survey_stamp(stamp)
    return {"ok": True, "result": finalized}
