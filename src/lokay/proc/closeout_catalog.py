"""Close out the whole AI-PR catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations

SLOTS = 30


def run(
    prepared: dict, *, pass_dir: str, config_path: str | None, live: bool
) -> dict:
    from lokay.passkit.working import load_begin_working
    from lokay.proc.closeout_pr_subflow import run as run_one
    from lokay.proc.record_pr_closeout_slot import record
    from lokay.proc.reduce_pr_closeout import reduce_state
    from lokay.proc.select_pr_closeout_slot import select

    if not prepared.get("ok"):
        return dict(prepared)
    repos = list(prepared.get("repos") or [])
    if len(repos) > SLOTS:
        return {
            "ok": False,
            "error": "PR closeout catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": SLOTS,
        }
    rows = []
    previous = {}
    for slot in range(1, len(repos) + 1):
        selected = select(prepared, previous, slot=slot)
        nested = {}
        if selected.get("route") == "closeout":
            nested = run_one(
                selected=selected, config_path=config_path, live=live
            )
            if not nested.get("ok"):
                return nested
        previous = record(selected, nested)
        rows.append(previous)
    _, working = load_begin_working(pass_dir)
    return reduce_state(prepared=prepared, rows=rows, working=working)
