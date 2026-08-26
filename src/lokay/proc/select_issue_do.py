"""Route do or skip from pick + sito classify. One job."""


def select(picked: dict, classified: dict) -> dict:
    if picked.get("route") != "issue":
        return {"ok": True, "route": "skip", "reason": "no_issue"}
    if classified.get("route") != "ready":
        return {
            "ok": True,
            "repo": picked.get("repo"),
            "issue": picked.get("issue"),
            "route": "skip",
            "reason": classified.get("reason") or "sito_nie_robic",
        }
    return {"ok": True, "route": "do", "repo": picked["repo"], "issue": picked["issue"]}
