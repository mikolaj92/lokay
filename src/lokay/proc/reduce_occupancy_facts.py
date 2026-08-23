"""Purely reduce merged and live-receipt reactions into occupancy facts."""


def reduce_state(*, prepared: dict, merged_clear: dict, results: list[dict]) -> dict:
    live = []
    cleared = list(merged_clear.get("cleared") or [])
    for row in results:
        repo = str(row.get("repo") or "")
        if row.get("route") == "occupied" and repo and repo not in live:
            live.append(repo)
        if row.get("route") == "closed" and row.get("cleared"):
            cleared.append(dict(row.get("receipt") or {}))
        if (
            row.get("route") == "closed"
            and not row.get("cleared")
            and repo
            and repo not in live
        ):
            live.append(repo)
    merged = list(prepared.get("merged") or [])
    return {
        "ok": True,
        "merged": merged,
        "live_repos": live,
        "occupied": list(dict.fromkeys([*merged, *live])),
        "cleared": cleared,
        "receipt_state_unknown": bool(prepared.get("receipt_state_unknown")),
        "live_receipt_count": len(live),
    }
