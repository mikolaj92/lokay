"""Persist one already-reduced conflict-resolution state."""

from lokay.passkit.working import load_begin_working, recount_prs, save_begin_working


def record(*, pass_dir: str, reduced: dict) -> dict:
    if reduced.get("route") == "none":
        return {"ok": True, "route": "none", "closed": 0}
    begin, _ = load_begin_working(pass_dir)
    state = dict(reduced)
    recount_prs(state)
    save_begin_working(pass_dir, begin, state)
    return {
        "ok": True,
        "route": str(state.get("conflict_route") or "failed"),
        "closed": int(state.get("conflict_closed") or 0),
        "merge_conflicts": int(state.get("conflict_route") == "failed"),
    }
