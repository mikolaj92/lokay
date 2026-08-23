"""Return the authored queue-conflict terminal result."""


def summarize(selected: dict, recorded: dict) -> dict:
    if selected.get("route") == "none":
        result = {"kept": 0, "skipped": 0, "demoted": 0, "needs_human": 0}
    else:
        route = str(recorded.get("route") or "needs_human")
        result = {
            "kept": int(route == "ready"),
            "skipped": int(route == "skip"),
            "demoted": int(route == "close"),
            "needs_human": int(route == "needs_human"),
        }
    return {"ok": True, "result": result}
