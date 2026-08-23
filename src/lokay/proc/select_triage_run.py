"""Stabilize the optional semantic triage subflow result."""


def select(gate: dict, run: dict) -> dict:
    if gate.get("route") == "blocked":
        return {"ok": True, "route": "blocked", **gate}
    if gate.get("route") != "run":
        return {"ok": True, "route": "none"}
    return {"ok": True, **gate, **run, "route": run.get("route") or "failed"}
