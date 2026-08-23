"""Persist one already-reduced PR survey state."""

from lokay.passkit.working import load_begin_working, save_begin_working


def persist(*, pass_dir: str, reduced: dict) -> dict:
    begin, _ = load_begin_working(pass_dir)
    state = dict(reduced["state"])
    save_begin_working(pass_dir, begin, state)
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "remaining_prs": state["remaining_prs"],
        "actionable_prs": state["actionable_prs"],
        "survey_errors": state["survey_errors"],
        "probe_failed": bool(state["pr_survey_failed"]),
        "skipped": bool(reduced.get("skipped")),
        "reason": "recent_empty" if reduced.get("skipped") else "",
    }
