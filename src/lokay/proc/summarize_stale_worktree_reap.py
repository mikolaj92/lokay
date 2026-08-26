"""Persist and return the authored stale-worktree subflow result."""

from lokay.passkit.working import load_begin_working, save_begin_working


def summarize(
    *, pass_dir: str, collected: dict, catalog: dict, live: bool
) -> dict:
    if catalog.get("skipped") or catalog.get("route") == "skip":
        result = {
            "pass_dir": pass_dir,
            "planned": not live,
            "kept": [],
            "reaped": [],
            "failed": [],
            "kept_count": 0,
            "reaped_count": 0,
            "deferred": list(collected.get("deferred") or []),
            "receipt_state_unknown": not bool(collected.get("receipt_safe", True)),
            "skipped": True,
            "reason": catalog.get("reason") or "skip",
            "count": catalog.get("count"),
            "slot_count": catalog.get("slot_count"),
        }
        return {"ok": True, "result": result}
    effects = list(catalog.get("effects") or [])
    rows = [dict(x.get("row") or {}) for x in effects if x.get("row")]
    kept = [x for x in rows if x.get("kept")]
    reaped = [x for x in rows if x.get("removed")]
    begin, working = load_begin_working(pass_dir)
    actions = list(working.get("actions") or [])
    actions.extend(
        {
            "step": (
                "reap_stale_worktree" if row.get("removed") else "keep_stale_worktree"
            ),
            **row,
        }
        for row in rows
    )
    working["actions"] = actions
    save_begin_working(pass_dir, begin, working)
    result = {
        "pass_dir": pass_dir,
        "planned": not live,
        "kept": kept,
        "reaped": reaped,
        "failed": [x for x in kept if x.get("reason") == "remove_failed"],
        "kept_count": len(kept) + len(collected.get("deferred") or []),
        "reaped_count": len(reaped),
        "deferred": list(collected.get("deferred") or []),
        "receipt_state_unknown": not bool(collected.get("receipt_safe", True)),
    }
    return {"ok": True, "result": result}
