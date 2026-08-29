"""Department receipt: a do issue becomes an open PR. Never a merge."""


def summarize(nest: dict) -> dict:
    result = nest.get("result") if isinstance(nest.get("result"), dict) else nest
    return {
        "ok": True,
        "department": "executor",
        "route": nest.get("route") or "idle",
        "merged": False,
        "result": {
            **dict(result or {}),
            "department": "executor",
            "merged": False,
        },
    }
