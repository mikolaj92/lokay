"""Check all authored untracked paths in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations

SLOTS = 30


def run(listed: dict) -> dict:
    """List already bounded; loop select/check then reduce."""
    from lokay.proc.check_self_repair_untracked_path import check
    from lokay.proc.reduce_self_repair_untracked_checks import reduce_state
    from lokay.proc.select_self_repair_untracked_slot import select

    if not listed.get("ok"):
        return dict(listed)
    rows = []
    for slot in range(1, SLOTS + 1):
        selected = select(listed, slot=slot)
        if selected.get("route") != "path":
            rows.append(selected)
            continue
        checked = check(selected)
        rows.append(checked)
        if checked.get("route") == "invalid" or not checked.get("ok"):
            break
    return reduce_state(rows, listed)
