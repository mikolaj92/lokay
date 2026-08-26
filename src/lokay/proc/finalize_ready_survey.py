"""Persist one already-reduced ready survey state."""

from lokay.passkit.io import survey_path, write_json
from lokay.passkit.working import load_begin_working, save_begin_working

SURVEY_KEYS = (
    "prs_by_repo",
    "inbox_by_repo",
    "inbox_issues_by_repo",
    "ready_by_repo",
    "pr_survey_failed",
    "inbox_survey_failed",
    "ready_survey_failed",
    "remaining_inbox",
    "remaining_ready",
    "remaining_ready_with_pr",
    "remaining_prs",
    "actionable_prs",
    "manual_prs",
    "survey_errors",
)


def finalize(*, pass_dir: str, reduced: dict) -> dict:
    begin, working = load_begin_working(pass_dir)
    working.update(
        {
            key: reduced[key]
            for key in (
                "actions",
                "progress",
                "ready_by_repo",
                "ready_survey_failed",
                "remaining_ready",
                "remaining_ready_with_pr",
                "survey_errors",
            )
        }
    )
    write_json(survey_path(pass_dir), {key: working.get(key) for key in SURVEY_KEYS})
    save_begin_working(pass_dir, begin, working)
    from lokay.proc.record_inflight_remaining import record

    try:
        record(pass_dir=pass_dir, state_path=str(begin.get("state_path") or "") or None)
    except OSError:
        pass
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "remaining_ready": reduced["remaining_ready"],
        "remaining_ready_with_pr": reduced["remaining_ready_with_pr"],
        "survey_errors": reduced["survey_errors"],
        "probe_failed": bool(reduced["ready_survey_failed"]),
        "skipped": bool(reduced.get("skipped")),
    }
