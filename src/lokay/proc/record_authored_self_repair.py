"""Stabilize performed or absent authored self-repair execution."""


def record(entry: dict, run: dict) -> dict:
    if run.get("route"):
        return run
    return {
        "ok": True,
        "route": "unused" if entry.get("route") != "run" else "terminal",
        "reason": entry.get("reason") or "fala_self_repair_failed",
        "path": {},
    }
