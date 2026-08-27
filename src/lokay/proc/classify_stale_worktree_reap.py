"""Classify leftover work-copy cleanup as a route. Never process.failed."""


def failed(error: object = None, reason: str = "stale_worktree_reap_failed") -> dict:
    """Classified child failure the parent when can read. Never process.failed."""
    if isinstance(error, BaseException):
        message = str(error).strip() or type(error).__name__
    elif error not in (None, "", {}):
        message = str(error)
    else:
        message = "empty stale_worktree_reap child"
    payload = {
        "ok": True,
        "route": "failed",
        "reason": reason,
        "error": message,
    }
    return {**payload, "result": dict(payload)}


def classify(out: object = None, error: object = None) -> dict:
    """Lift a child envelope or turn throw / empty / not-ok into route=failed."""
    if error is not None:
        return failed(error)
    if not isinstance(out, dict) or not out:
        return failed("empty stale_worktree_reap child")
    if not out.get("ok"):
        return failed(out.get("error") or out.get("reason") or out)
    route = str(out.get("route") or "")
    result = out.get("result")
    if isinstance(result, dict):
        route = route or str(result.get("route") or "")
        if result.get("skipped"):
            route = route or "skip"
    if not route:
        if isinstance(result, dict) and result:
            route = "cleaned"
        else:
            return failed(out.get("error") or "empty stale_worktree_reap child")
    payload = {
        "ok": True,
        "route": route,
        "reason": out.get("reason"),
        "result": dict(result) if isinstance(result, dict) else {"route": route},
    }
    if out.get("error") not in (None, "", {}):
        payload["error"] = out.get("error")
    return payload
