"""Purely classify the closed result of one authored self-repair graph."""


def classify(run: dict) -> dict:
    path = run.get("path") or {}
    if run.get("route") != "classify" or not path.get("ok"):
        return {
            "ok": True,
            "route": "terminal",
            "reason": run.get("reason")
            or path.get("reason")
            or "fala_self_repair_failed",
            "path": path,
        }
    return {
        "ok": True,
        "route": "restart" if path.get("restart_required") else "terminal",
        "reason": "" if path.get("restart_required") else "restart_not_required",
        "path": path,
    }
