"""Classify issue-to-PR delivery as a route. Never process.failed."""


def failed(error: object = None, reason: str = "issue_to_pr_failed") -> dict:
    """Classified child failure the parent when can read. Never process.failed."""
    if isinstance(error, BaseException):
        message = str(error).strip() or type(error).__name__
    elif error not in (None, "", {}):
        message = str(error)
    else:
        message = "empty issue_to_pr_delivery child"
    payload = {
        "ok": True,
        "route": "failed",
        "reason": reason,
        "error": message,
    }
    return {**payload, "result": dict(payload)}


def classify(out: object = None, error: object = None) -> dict:
    """Lift a child envelope or turn throw / empty / not-ok into a route."""
    if error is not None:
        return failed(error)
    if not isinstance(out, dict) or not out:
        return failed("empty issue_to_pr_delivery child")
    if not out.get("ok"):
        return failed(out.get("error") or out.get("reason") or out)
    result = out.get("result")
    route = str(out.get("route") or "")
    if isinstance(result, dict):
        route = route or str(result.get("route") or "")
        if result.get("skipped"):
            route = route or "skip"
    if not route:
        pr = out.get("pr")
        if pr in (None, "", 0) and isinstance(result, dict):
            pr = result.get("pr")
        delivered = out.get("delivered")
        if delivered is None and isinstance(result, dict):
            delivered = result.get("delivered")
        if pr not in (None, "", 0) or delivered:
            route = "deliver"
        elif isinstance(result, dict) and result.get("stopped"):
            route = "no_effect"
        elif isinstance(result, dict) and result:
            route = "no_effect"
        else:
            return failed(out.get("error") or "empty issue_to_pr_delivery child")
    payload = {
        "ok": True,
        "route": route,
        "reason": out.get("reason"),
        "result": dict(result) if isinstance(result, dict) else {"route": route},
    }
    for key in ("pr", "branch", "delivered", "stopped"):
        if out.get(key) not in (None, "", {}):
            payload[key] = out.get(key)
    if out.get("error") not in (None, "", {}):
        payload["error"] = out.get("error")
    return payload
