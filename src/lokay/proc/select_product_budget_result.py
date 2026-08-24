"""Select the first authored terminal from bounded pass slots."""


def select(prepared: dict, rows: list[dict]) -> dict:
    for row in rows:
        if row.get("route") == "terminal":
            return {"ok": True, "result": row["payload"]}
    return {"ok": False, "error": "product pass budget ended without terminal"}
