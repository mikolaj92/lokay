"""Return one explicit terminal PR-repair outcome."""


def terminal(decision: dict, *, kind: str) -> dict:
    return {"ok": True, "terminal": kind, "decision": decision}
