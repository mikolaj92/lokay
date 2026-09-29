"""Department receipt: marks and children only. Zero ai/fix."""


def summarize(nest: dict, listed: dict | None = None) -> dict:
    result = nest.get("result") if isinstance(nest.get("result"), dict) else nest
    payload = {
        **dict(result or {}),
        "launched": None,
        "department": "issue_triage",
    }
    if isinstance(listed, dict) and list(listed.get("issues") or []):
        payload["listed"] = listed
    return {
        "ok": True,
        "department": "issue_triage",
        "route": nest.get("route") or "idle",
        "launched": None,
        "result": payload,
    }
