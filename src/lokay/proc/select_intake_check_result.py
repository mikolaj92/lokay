"""Select the sole succeeded mechanical intake-check branch."""


def select(*facts: dict) -> dict:
    chosen = [x for x in facts if x.get("route") == "selected"]
    if len(chosen) == 1:
        return chosen[0]
    failure = next((x for x in facts if x.get("route") == "terminal"), None)
    return {
        "ok": True,
        "route": "terminal",
        "reason": (failure or {}).get("reason") or "intake_check_result_missing",
        "error": (failure or {}).get("error"),
    }
