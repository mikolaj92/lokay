"""Return the authored terminal result of one triage dispatch subflow."""


def summarize(recorded: dict) -> dict:
    return {"ok": True, "result": {"ran": int(recorded.get("ran") or 0)}}
