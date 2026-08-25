"""Select one closed self-repair entry result."""


def select(prepared: dict, entry: dict, outcome: dict, marker: dict) -> dict:
    base = {
        "issue": prepared.get("issue"),
        "incident_url": prepared.get("incident_url"),
        "gate_released": False,
    }
    if entry.get("route") == "terminal":
        return {
            "ok": True,
            "route": "failure",
            "reason": entry.get("reason"),
            "result": {
                "ok": False,
                "health": "self_repair_failed",
                "reason": entry.get("reason"),
                **base,
            },
        }
    path = outcome.get("path") or {}
    if outcome.get("route") == "restart" and marker.get("route") == "written":
        return {
            "ok": True,
            "route": "success",
            "commit": path.get("commit"),
            "result": {
                **path,
                "ok": True,
                "health": "restart_required",
                "gate_released": bool(
                    path.get("gate_released") or path.get("restart_required")
                ),
                **{k: v for k, v in base.items() if k not in path},
            },
        }
    reason = marker.get("reason") or outcome.get("reason") or "fala_self_repair_failed"
    return {
        "ok": True,
        "route": "failure",
        "reason": reason,
        "result": {
            "ok": False,
            "health": "self_repair_failed",
            "reason": reason,
            "error": marker.get("error"),
            **base,
        },
    }
