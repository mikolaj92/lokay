"""Purely reduce all explicit untracked-path checks."""


def reduce_state(rows: list[dict], listed: dict) -> dict:
    invalid = next((x for x in rows if x.get("route") == "invalid"), None)
    return {
        **listed,
        "ok": invalid is None,
        "route": "tracked" if invalid is None else "invalid",
        "error": "" if invalid is None else invalid.get("error"),
    }
