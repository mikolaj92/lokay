"""Return the authored stale-stage recovery terminal result."""


def summarize(prepared: dict, updated: dict) -> dict:
    if prepared.get("route") == "recent_empty":
        result = {
            "ok": True,
            "planned": False,
            "applied": False,
            "reaped": [],
            "kept": [],
            "reaped_count": 0,
            "pass_dir": prepared.get("pass_dir", ""),
            "skipped": True,
            "reason": "recent_empty",
            "probe_failed": False,
        }
    else:
        result = {
            "ok": True,
            "planned": not updated.get("apply") if updated.get("reaped") else True,
            "applied": bool(updated.get("apply")),
            "probe_failed": bool(updated.get("probe_failed")),
            "reaped": list(updated.get("reaped") or []),
            "kept": [],
            "reaped_count": int(updated.get("reaped_count") or 0),
            "pass_dir": prepared.get("pass_dir", ""),
        }
    return {"ok": True, "result": result}
