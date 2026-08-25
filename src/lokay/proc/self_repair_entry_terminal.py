"""Return the selected closed self-repair entry result."""


def terminal(selected: dict) -> dict:
    return {
        "ok": True,
        "result": selected.get("result")
        or {
            "ok": False,
            "health": "self_repair_failed",
            "reason": "entry_result_missing",
        },
    }
