"""Stabilize explicit optional factory-begin terminals."""


def select(rows: list[dict]) -> dict:
    for row in rows:
        if row.get("ok") and row.get("result") is not None:
            return {"ok": True, "result": row["result"]}
    return {"ok": False, "error": "factory begin ended without terminal"}
