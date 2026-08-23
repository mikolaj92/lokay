"""Return the authored catalog PR-closeout terminal result."""


def summarize(persisted: dict) -> dict:
    return {"ok": True, "result": persisted} if persisted.get("ok") else persisted
