"""Apply keep/remove for the stale-worktree catalog (no leftover labels)."""

from __future__ import annotations

SLOTS = 4


def overflow_bound(present: list[dict]) -> list[dict]:
    """One job: bound this pass to authored slots; never skip the whole catalog."""
    return list(present)[:SLOTS]


def apply_slot(
    collected: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
    """One job: classify one slot, then keep or remove that worktree."""
    from lokay.proc.classify_stale_worktree_candidate import classify
    from lokay.proc.keep_stale_worktree_candidate import apply as keep
    from lokay.proc.remove_stale_worktree_candidate import apply as remove

    candidate = dict(collected.get(f"candidate_{slot}") or {})
    classified = classify(candidate, live=live)
    if classified.get("route") == "keep":
        return keep(classified)
    if classified.get("route") == "remove":
        return remove(classified, config_path=config_path, live=live)
    return classified


def run(collected: dict, *, config_path: str | None, live: bool) -> dict:
    if not collected.get("ok"):
        return dict(collected)
    present = [
        row
        for row in list(collected.get("candidates") or [])
        if isinstance(row, dict) and row.get("present")
    ]
    bounded = overflow_bound(present)
    # Rebuild authored candidate_* from the bound present rows so overflow
    # never blanks the whole catalog. Absent fillers keep slot count stable.
    working = dict(collected)
    for slot in range(1, SLOTS + 1):
        if slot <= len(bounded):
            row = dict(bounded[slot - 1])
            row["slot"] = slot
            working[f"candidate_{slot}"] = row
        else:
            working[f"candidate_{slot}"] = {"present": False, "slot": slot}
    effects = [
        apply_slot(working, slot=slot, config_path=config_path, live=live)
        for slot in range(1, SLOTS + 1)
    ]
    failed = next((row for row in effects if not row.get("ok", True)), None)
    if failed is not None:
        return dict(failed)
    return {
        "ok": True,
        "effects": effects,
        "bounded": len(present) > SLOTS,
        "present_count": len(present),
        "slot_count": SLOTS,
    }
