"""Purely deduplicate bounded CLOSED ready-label candidates."""


def reduce_candidates(prepared: dict, rows: list[dict], *, slot_count: int) -> dict:
    unique = []
    seen = set()
    for row in rows:
        for item in row.get("candidates") or []:
            key = (str(item["repo"]), int(item["number"]))
            if key not in seen:
                seen.add(key)
                unique.append({"repo": key[0], "number": key[1]})
    if len(unique) > slot_count:
        return {
            "ok": True,
            "route": "mutate" if prepared.get("route") == "probe" else "skip",
            "skipped": False,
            "leftover_skip": True,
            "leftover_overflow": True,
            "reason": "leftover_overflow",
            "count": len(unique),
            "slot_count": slot_count,
            "candidates": unique[:slot_count],
            "failed_repos": [
                str(x.get("repo") or "") for x in rows if x.get("route") == "failed"
            ],
            "mutations_allowed": bool(prepared.get("mutations_allowed")),
            "live": bool(prepared.get("live")),
        }
    failed = [str(x.get("repo") or "") for x in rows if x.get("route") == "failed"]
    return {
        "ok": True,
        "route": "mutate" if prepared.get("route") == "probe" else "skip",
        "candidates": unique,
        "failed_repos": failed,
        "mutations_allowed": bool(prepared.get("mutations_allowed")),
        "live": bool(prepared.get("live")),
    }
