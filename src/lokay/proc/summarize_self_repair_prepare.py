"""Return the authored self-repair prepare terminal result."""


def summarize(selected: dict) -> dict:
    return {"ok": True, "result": selected} if selected.get("ok") else selected
