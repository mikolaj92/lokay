"""Purely combine repository probes into bounded unique candidates."""


def reduce_state(*, prepared: dict, rows: list[dict], candidate_slots: int) -> dict:
    failed = any(x.get("route") == "failed" for x in rows)
    candidates = []
    seen = set()
    for row in rows:
        for item in row.get("issues") or []:
            key = (item["repo"], int(item["issue"]))
            if key not in seen:
                seen.add(key)
                candidates.append(dict(item))
    if len(candidates) > candidate_slots:
        return {
            "ok": False,
            "error": "stale implementing candidates exceed authored slots",
            "candidates": len(candidates),
            "slot_count": candidate_slots,
        }
    return {
        "ok": True,
        "route": "candidates" if candidates else "empty",
        "candidates": candidates,
        "probe_failed": failed,
        "probed": any(x.get("route") in {"probed", "failed"} for x in rows),
        "stamp": prepared.get("stamp", ""),
    }
