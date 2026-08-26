"""Return the authored queue-conflict terminal result."""


def summarize(selected: dict, recorded: dict, advanced: dict | None = None) -> dict:
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
    nxt = dict(advanced or {})
    if nxt.get("advanced"):
        result["clean_repos"] = list(nxt.get("clean_repos") or [])
        if nxt.get("route") == "candidate":
            result["selected"] = {
                "repo": nxt.get("repo"),
                "issue": nxt.get("issue"),
                "candidate": nxt.get("candidate"),
            }
    return {"ok": True, "result": result}
