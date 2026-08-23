"""Return the authored one-PR closeout terminal result."""


def summarize(finalized: dict) -> dict:
    return {"ok": True, "result": finalized} if finalized.get("ok") else finalized
