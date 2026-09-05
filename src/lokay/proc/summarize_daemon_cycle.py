"""Return the authored daemon-cycle terminal envelope."""


def summarize(*, lokay_node: dict, repair: dict) -> dict:
    lokay = lokay_node.get("factory")
    if not isinstance(lokay, dict):
        return {"ok": False, "error": "daemon cycle completed without factory envelope"}
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
    return {"ok": True, "result": lokay}
