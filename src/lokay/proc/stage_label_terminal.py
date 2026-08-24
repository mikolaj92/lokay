"""Select one closed issue-stage transition result."""


def terminal(
    prepared: dict,
    issue: dict,
    classified: dict,
    removed: dict,
    added: dict,
    commented: dict,
) -> dict:
    common = {
        "repo": prepared.get("repo"),
        "issue": prepared.get("issue"),
        "stage": prepared.get("stage"),
        "add_labels": prepared.get("add_labels") or [],
        "remove_labels": prepared.get("remove_labels") or [],
    }
    if classified.get("route") == "terminal":
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": False,
                "applied": False,
                "skipped": True,
                "reason": classified.get("reason"),
                "issue_state": classified.get("issue_state"),
                "receipt": False,
                **common,
            },
        }
    failure = next(
        (x for x in (removed, added, commented) if x.get("route") == "terminal"), None
    )
    if failure:
        return {
            "ok": True,
            "result": {
                "ok": False,
                "reason": failure.get("reason"),
                "error": failure.get("error") or failure.get("reason"),
                "applied": False,
                **common,
            },
        }
    return {
        "ok": True,
        "result": {
            "ok": True,
            "planned": not prepared.get("live"),
            "applied": bool(prepared.get("live")),
            "receipt": bool(prepared.get("comment")),
            **common,
        },
    }
