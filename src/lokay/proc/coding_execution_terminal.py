"""Lift the closed coding result for the parent delivery node."""


def terminal(finalized: dict, manual: dict) -> dict:
    route = str(finalized.get("route") or "human")
    payload = {
        "ok": True,
        "route": route,
        "decision": dict(finalized.get("decision") or {}),
        "evidence_kind": str(finalized.get("evidence_kind") or "none"),
        "reason": finalized.get("reason") or manual.get("reason"),
    }
    return {**payload, "result": dict(payload)}
