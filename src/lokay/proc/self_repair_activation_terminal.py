"""Select one closed self-repair activation result."""


def terminal(
    prepared: dict,
    checkout: dict,
    dirty: dict,
    fetch: dict,
    merged: dict,
    head: dict,
    classified: dict,
    head_ancestor: dict,
    origin_ancestor: dict,
) -> dict:
    common = {"commit": prepared.get("commit"), "path": prepared.get("path")}
    if prepared.get("route") == "planned":
        return {
            "ok": True,
            "result": {"ok": True, "planned": True, "activated": False, **common},
        }
    if checkout.get("route") == "dirty" and dirty.get("route") == "published":
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": False,
                "activated": False,
                "published": True,
                "reason": "dirty_tree",
                **common,
            },
        }
    if classified.get("route") == "exact":
        return {
            "ok": True,
            "result": {"ok": True, "planned": False, "activated": True, **common},
        }
    if (
        head_ancestor.get("route") == "ancestor"
        or origin_ancestor.get("route") == "ancestor"
    ):
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": False,
                "activated": True,
                "published": True,
                "reason": "already_on_main",
                "head": head.get("head"),
                **common,
            },
        }
    reason = (
        classified.get("reason")
        or dirty.get("reason")
        or fetch.get("reason")
        or merged.get("reason")
        or head.get("reason")
        or prepared.get("reason")
        or "commit_not_activated"
    )
    return {
        "ok": True,
        "result": {
            "ok": False,
            "planned": False,
            "activated": False,
            "reason": reason,
            "error": reason.replace("_", " "),
            **common,
        },
    }
