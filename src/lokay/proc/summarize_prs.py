"""Receipt for one PRs parent pass."""


def summarize(
    picked: dict,
    triage_run: dict,
    repair_gate: dict | None = None,
    repair_run: dict | None = None,
) -> dict:
    gate = dict(repair_gate or {})
    repair = dict(repair_run or {})
    return {
        "ok": True,
        "result": {
            "pr": picked.get("pr"),
            "repo": picked.get("repo"),
            "route": picked.get("route") or "none",
            "reason": picked.get("reason"),
            "triaged": triage_run.get("route"),
            "repair_route": gate.get("route"),
            "repair_reason": gate.get("reason"),
            "repaired": repair.get("route") == "completed",
        },
    }
