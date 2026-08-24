"""Purely flatten bounded repository probes into orphan-ready candidates."""


def reduce_candidates(prepared: dict, rows: list[dict], *, slot_count: int) -> dict:
    candidates = [item for row in rows for item in row.get("candidates") or []]
    failed = [
        str(row.get("repo") or "") for row in rows if row.get("route") == "failed"
    ]
    if len(candidates) > slot_count:
        return {
            "ok": False,
            "error": "ready hygiene candidates exceed authored slots",
            "count": len(candidates),
            "slot_count": slot_count,
        }
    return {
        "ok": True,
        "route": "skip" if prepared.get("route") == "skip" else "mutate",
        "candidates": candidates,
        "failed_repos": failed,
        "mutations_allowed": bool(prepared.get("mutations_allowed")),
        "live": bool(prepared.get("live")),
    }
