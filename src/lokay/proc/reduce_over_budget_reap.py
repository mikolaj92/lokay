"""Purely reduce bounded receipt outcomes into the terminal reaction."""


def reduce_state(*, rows: list[dict], budget_s: int) -> dict:
    reaped = []
    kept = []
    for row in rows:
        base = {
            k: row.get(k)
            for k in ("repo", "issue", "pid", "elapsed_s")
            if row.get(k) is not None
        }
        if row.get("route") == "reaped":
            reaped.append(
                {
                    **base,
                    "budget_s": budget_s,
                    "killed": bool(row.get("killed")),
                    "reason": row.get("reason"),
                    **({"park": row["park"]} if row.get("park") else {}),
                }
            )
        elif row.get("route") in {"keep", "kept", "harvested"}:
            kept.append(
                {
                    **base,
                    **({"reason": row.get("reason")} if row.get("reason") else {}),
                    **({"pr": row.get("pr")} if row.get("pr") else {}),
                }
            )
    return {
        "ok": True,
        "reaped": reaped,
        "kept": kept,
        "reaped_count": len(reaped),
        "budget_s": budget_s,
    }
