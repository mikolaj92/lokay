"""Reduce up to two explicit label probes for one repository."""


def record(selected: dict, rows: list[dict]) -> dict:
    candidates = []
    failed = False
    for row in rows:
        candidates.extend(row.get("candidates") or [])
        failed = failed or row.get("route") == "failed"
    return {
        "ok": True,
        "route": (
            "failed"
            if failed
            else ("record" if selected.get("route") == "labels" else "empty")
        ),
        "repo": str(selected.get("repo") or ""),
        "candidates": candidates,
    }
