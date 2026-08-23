"""Return the authored self-repair terminal envelope."""


def summarize(*, preflight: dict, push: dict, activate: dict, close: dict) -> dict:
    commit = str(
        preflight.get("commit") or push.get("commit") or activate.get("commit") or ""
    )
    validated = preflight.get("validated") is True
    restart = preflight.get("restart_required") is True
    published_dirty = (
        activate.get("published") is True
        and str(activate.get("reason") or "") == "dirty_tree"
    )
    released = bool(validated and restart)
    result = {
        "validated": validated or published_dirty,
        "restart_required": restart or published_dirty,
        "commit": commit or None,
        "incident_closed": close.get("closed") is True,
        "gate_released": released,
    }
    if published_dirty and not released:
        result.update(ok=True, reason="published_push_kept_dirty_tree")
    elif not result["validated"] or not result["restart_required"]:
        result.update(ok=False, error="self-repair did not validate activated main")
    return {"ok": True, "result": result}
