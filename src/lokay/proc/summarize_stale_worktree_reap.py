"""Persist the stale-worktree child result, or lift a catalog skip."""

from lokay.passkit.working import load_begin_working, save_begin_working


def skip_result(*, pass_dir: str, collected: dict, catalog: dict, live: bool) -> dict | None:
    """One job: lift catalog overflow skip so the child does not fail closed."""
    if not (catalog.get("skipped") or catalog.get("route") == "skip"):
        return None
    return {
        "ok": True,
        "result": {
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
        },
    }


def persist_result(*, pass_dir: str, collected: dict, catalog: dict, live: bool) -> dict:
    """One job: write keep/remove rows into the pass working ledger."""
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
    return {
        "ok": True,
        "result": {
            "pass_dir": pass_dir,
            "planned": not live,
            "kept": kept,
            "reaped": reaped,
            "failed": [x for x in kept if x.get("reason") == "remove_failed"],
            "kept_count": len(kept) + len(collected.get("deferred") or []),
            "reaped_count": len(reaped),
            "deferred": list(collected.get("deferred") or []),
            "receipt_state_unknown": not bool(collected.get("receipt_safe", True)),
        },
    }


def summarize(
    *, pass_dir: str, collected: dict, catalog: dict, live: bool
) -> dict:
    skipped = skip_result(
        pass_dir=pass_dir, collected=collected, catalog=catalog, live=live
    )
    if skipped is not None:
        return skipped
    return persist_result(
        pass_dir=pass_dir, collected=collected, catalog=catalog, live=live
    )
