"""Build exact validator feedback for the single allowed localization retry."""


def build(validated: dict) -> dict:
    if validated.get("route") != "invalid":
        return {"ok": True, "route": "unused", "feedback": ""}
    error = str(validated.get("validator_error") or "unknown validation error")
    return {
        "ok": True,
        "route": "retry",
        "feedback": f"\n\nYour previous JSON was invalid: {error}. Return ONLY the required JSON object.",
    }
