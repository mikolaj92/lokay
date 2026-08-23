"""Emit one explicit KEEP effect for a classified worktree."""


def apply(classified: dict) -> dict:
    row = dict(classified.get("row") or {})
    row["kept"] = True
    return {"ok": True, "applied": True, "row": row}
