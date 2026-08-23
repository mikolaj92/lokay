"""Purely reduce stale-stage effects into truthful counts."""


def reduce_state(*, probe: dict, gate: dict, rows: list[dict]) -> dict:
    reaped = []
    for row in rows:
        if row.get("route") not in {"apply", "applied", "plan", "failed"}:
            continue
        staged = dict(
            row.get("staged") or {"ok": True, "planned": True, "stage": "ready"}
        )
        reaped.append(
            {
                "repo": row["repo"],
                "issue": int(row["issue"]),
                "label": row.get("label"),
                **staged,
            }
        )
    removed = [x for x in reaped if not x.get("planned")]
    return {
        "ok": True,
        "probe_failed": bool(probe.get("probe_failed")),
        "probed": bool(probe.get("probed")),
        "apply": bool(gate.get("apply")),
        "reaped": reaped,
        "reaped_count": len(removed),
        "stamp": probe.get("stamp", ""),
    }
