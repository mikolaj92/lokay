"""Return the authored conflict-resolution terminal result."""


def summarize(recorded: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "closed": int(recorded.get("closed") or 0),
            "merge_conflicts": int(recorded.get("merge_conflicts") or 0),
        },
    }
