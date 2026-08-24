"""Select one explicit factory-begin terminal kind."""


def classify(lease: dict, recheck: dict, preflight: dict, mode: dict) -> dict:
    if lease.get("route") == "terminal" or recheck.get("route") == "terminal":
        kind = "preflight_failed"
    elif preflight.get("route") == "terminal":
        kind = "preflight_failed"
    elif mode.get("reason") == "mode_not_live":
        kind = "mode_not_live"
    elif mode.get("reason") == "offline":
        kind = "offline"
    else:
        kind = "ready"
    return {"ok": True, "kind": kind}
