"""Stabilize four optional authored local-test terminals."""


def select(rows: list[dict]) -> dict:
    for row in rows:
        if row.get("ok") and row.get("result") is not None:
            return {"ok": True, "result": row["result"]}
    return {"ok": False, "error": "local test path ended without terminal"}
