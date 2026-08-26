"""Classify and keep/remove the stale-worktree catalog in one atom (no 4-slot unroll)."""

from __future__ import annotations

SLOTS = 4


def _one_slot(
    collected: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
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
    if len(present) > SLOTS:
        return {
            "ok": True,
            "route": "skip",
            "skipped": True,
            "reason": "stale_worktree_overflow",
            "count": len(present),
            "slot_count": SLOTS,
            "effects": [],
        }
    effects = [
        _one_slot(collected, slot=slot, config_path=config_path, live=live)
        for slot in range(1, SLOTS + 1)
    ]
    failed = next((row for row in effects if not row.get("ok", True)), None)
    if failed is not None:
        return dict(failed)
    return {"ok": True, "effects": effects}
