"""Select one authored detached-worker receipt slot."""


def select(prepared: dict, *, slot: int) -> dict:
    rows = list(prepared.get("receipts") or [])
    if slot < 1 or slot > len(rows):
        return {"ok": True, "route": "empty", "slot": slot}
    row = dict(rows[slot - 1])
    try:
        repo = str(row.get("repo") or "")
        issue = int(row["issue"])
        pid = int(row["pid"])
    except (KeyError, TypeError, ValueError):
        return {"ok": True, "route": "invalid", "slot": slot}
    return {
        "ok": True,
        "route": "receipt" if repo and pid > 0 else "invalid",
        "slot": slot,
        "repo": repo,
        "issue": issue,
        "pid": pid,
        "receipt": row,
    }
