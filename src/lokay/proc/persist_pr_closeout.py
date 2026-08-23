"""Persist one already-reduced catalog PR closeout state."""

from lokay.passkit.working import load_begin_working, save_begin_working


def persist(*, pass_dir: str, reduced: dict) -> dict:
    if not reduced.get("ok"):
        return reduced
    begin, _ = load_begin_working(pass_dir)
    begin["repair_budget"] = int(reduced.get("repair_budget") or 0)
    state = dict(reduced["state"])
    save_begin_working(pass_dir, begin, state)
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "remaining_prs": state["remaining_prs"],
        "actionable_prs": state["actionable_prs"],
        "needs_repair": state["needs_repair"],
        "mergeable_green": state["mergeable_green"],
        "merge_disabled": state["merge_disabled"],
    }
