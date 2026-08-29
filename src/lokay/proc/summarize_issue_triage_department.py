"""Department receipt: marks and children only. Zero ai/fix."""


def summarize(nest: dict) -> dict:
    result = nest.get("result") if isinstance(nest.get("result"), dict) else nest
    return {
        "ok": True,
        "department": "issue_triage",
        "route": nest.get("route") or "idle",
        "launched": None,
        "result": {
            **dict(result or {}),
            "launched": None,
            "department": "issue_triage",
        },
    }
