"""Receipt envelope for one issues child pass. Does not write."""


def summarize(picked: dict, do: dict, launched: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "issue": picked.get("issue"),
            "repo": picked.get("repo"),
            "route": str(do.get("route") or picked.get("route") or "none"),
            "reason": do.get("reason") or picked.get("reason"),
            "launched": launched.get("route"),
        },
    }
