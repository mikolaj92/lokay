"""Apply the empty-survey TTL effect after PR survey persistence."""

from lokay.passkit.working import load_begin_working
from lokay.proc.survey_ttl import clear_survey_stamp, survey_stamp_path


def update(*, pass_dir: str, persisted: dict) -> dict:
    begin, _ = load_begin_working(pass_dir)
    stamp = survey_stamp_path(begin)
    if (
        stamp
        and not persisted.get("skipped")
        and (
            persisted.get("remaining_prs")
            or persisted.get("survey_errors")
            or persisted.get("probe_failed")
        )
    ):
        clear_survey_stamp(stamp)
    return {"ok": True, "result": persisted}
