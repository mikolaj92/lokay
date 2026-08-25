"""Select one closed daemon-entry outcome."""


def terminal(classified: dict, product: dict, repair: dict) -> dict:
    route = classified.get("route")
    preflight = classified.get("preflight") or {}
    if route == "product":
        return {
            "ok": True,
            "result": product.get("payload")
            or {"ok": False, "health": "product_result_missing"},
        }
    if route == "overlap":
        return {
            "ok": True,
            "result": {
                "ok": False,
                "health": "overlap",
                "code": "overlap",
                "error": "preflight skipped; overlapping run",
                "preflight": preflight,
            },
        }
    if route == "carrier_failed":
        return {
            "ok": True,
            "result": {
                "ok": False,
                "health": "carrier_failed",
                "error": "carrier preflight failed; self-repair and product work blocked",
                "preflight": preflight,
            },
        }
    outcome = repair.get("repair") or {}
    if repair.get("route") == "restart":
        return {
            "ok": True,
            "result": {
                "ok": False,
                "health": "self_repair_restart_required",
                "error": "self-repair validated; restart required before product work",
                "self_repair": outcome,
            },
        }
    return {
        "ok": True,
        "result": {
            "ok": False,
            "health": "self_repair_failed",
            "error": "preflight failed; dedicated self-repair did not release gate",
            "preflight": preflight,
            "self_repair": outcome,
        },
    }
