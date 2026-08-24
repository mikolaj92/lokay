"""Purely reduce bounded leftover-closeout effects."""


def reduce_state(prepared: dict, candidates: dict, rows: list[dict]) -> dict:
    closed = [
        {
            "repo": x["repo"],
            "issue": x["number"],
            **({"planned": True} if x.get("route") == "planned" else {}),
        }
        for x in rows
        if x.get("route") in {"removed", "planned"}
    ]
    removed = [x for x in closed if not x.get("planned")]
    skip = prepared.get("route") == "skip"
    failed = list(candidates.get("failed_repos") or [])
    return {
        "ok": True,
        "leftover_closed": len(removed),
        "labels_removed": bool(removed),
        "issue_to_pr_started": 0,
        "closed_out": closed,
        "planned": (
            not bool(candidates.get("mutations_allowed"))
            if closed
            else not bool(prepared.get("live"))
        ),
        "applied": bool(candidates.get("mutations_allowed")) if closed else False,
        "probe_failed": bool(failed),
        "failed_repos": failed,
        "skipped": skip,
        "reason": "recent_empty" if skip else "",
    }
