"""Return only the final harvested ledger from the authored subflow."""


def terminal(facts: dict) -> dict:
    return {
        "ok": True,
        "result": {
            "ok": True,
            "stuck_path": facts["stuck_path"],
            "stuck": facts.get("stuck") or {},
        },
    }
