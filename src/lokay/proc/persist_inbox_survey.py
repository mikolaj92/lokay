"""Persist one already-reduced inbox survey state."""

from lokay.passkit.working import load_begin_working, save_begin_working


def persist(*, pass_dir: str, reduced: dict) -> dict:
    begin, _ = load_begin_working(pass_dir)
    state = dict(reduced["state"])
    save_begin_working(pass_dir, begin, state)
    from lokay.proc.record_inflight_remaining import record

    try:
        record(pass_dir=pass_dir, state_path=str(begin.get("state_path") or "") or None)
    except OSError:
        pass
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "remaining_inbox": state["remaining_inbox"],
        "survey_errors": state["survey_errors"],
        "probe_failed": bool(state["inbox_survey_failed"]),
        "skipped": bool(reduced.get("skipped")),
        "reason": "recent_empty" if reduced.get("skipped") else "",
    }
