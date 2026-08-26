"""Receipt for one issues child pass."""


def summarize(picked: dict, do: dict, launched: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "issue": picked.get("issue"),
            "repo": picked.get("repo"),
            "route": do.get("route") or picked.get("route") or "none",
            "launched": launched.get("route"),
        },
    }
