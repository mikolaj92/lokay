"""Purely reduce candidate effects into one hygiene result."""


def reduce_state(prepared: dict, candidates: dict, rows: list[dict]) -> dict:
    cleaned = [
        {
            "repo": x["repo"],
            "issue": x["number"],
            **({"planned": True} if x.get("route") == "planned" else {}),
        }
        for x in rows
        if x.get("route") in {"removed", "planned"}
    ]
    removed = [x for x in cleaned if not x.get("planned")]
    skip = prepared.get("route") == "skip"
    failed = list(candidates.get("failed_repos") or [])
    return {
        "ok": True,
        "planned": (
            not bool(candidates.get("mutations_allowed"))
            if cleaned
            else not bool(prepared.get("live"))
        ),
        "applied": bool(candidates.get("mutations_allowed")) if cleaned else False,
        "probe_failed": bool(failed),
        "failed_repos": failed,
        "cleaned": cleaned,
        "cleaned_count": len(removed),
        "skipped": skip,
        "reason": "recent_empty" if skip else "",
    }
