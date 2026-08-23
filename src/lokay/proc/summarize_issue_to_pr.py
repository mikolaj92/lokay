"""Return the authored issue-to-PR gate terminal envelope."""


def summarize(*, delivery: dict, closeout: dict, no_effect: dict) -> dict:
    if delivery.get("pr") not in (None, "", 0):
        return {
            "ok": True,
            "result": {
                "pr": delivery["pr"],
                "branch": delivery.get("branch"),
                "delivered": True,
            },
        }
    reason = no_effect.get("reason") or (
        "delivery_pr_exists" if closeout.get("delivered") else "no_delivery"
    )
    return {
        "ok": True,
        "result": {
            "stopped": True,
            "reason": reason,
            "delivered": bool(closeout.get("delivered")),
        },
    }
