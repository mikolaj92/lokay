"""Return the authored daemon-cycle terminal envelope."""


def summarize(*, mill_node: dict, repair: dict) -> dict:
    mill = mill_node.get("mill")
    if not isinstance(mill, dict):
        return {"ok": False, "error": "daemon cycle completed without Lokay envelope"}
    if repair.get("restart_required") is True:
        return {
            "ok": True,
            "result": {
                "ok": False,
                "health": "self_repair_restart_required",
                "error": "confirmed stall repaired; restart required before product work",
                "self_repair": repair,
            },
        }
    return {"ok": True, "result": mill}
