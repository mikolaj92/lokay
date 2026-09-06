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
    # Existing open/merged delivery closeout is path success — never stopped /
    # condition_not_met (Fala skip noise on the unused no_effect edge).
    close_pr = closeout.get("pr")
    if closeout.get("delivered") or close_pr not in (None, "", 0):
        return {
            "ok": True,
            "result": {
                "pr": close_pr,
                "delivered": True,
                "closeout": True,
                "reason": closeout.get("reason") or "delivery_pr_exists",
            },
        }
    reason = no_effect.get("reason")
    if reason in (None, "", "condition_not_met"):
        reason = "no_delivery"
    return {
        "ok": True,
        "result": {
            "stopped": True,
            "reason": reason,
            "delivered": False,
        },
    }
