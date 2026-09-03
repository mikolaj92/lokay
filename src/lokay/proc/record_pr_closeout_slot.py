"""Stabilize one authored closeout slot and its nested result."""


def record(selected: dict, nested: dict) -> dict:
    slot = selected.get("slot")
    repo = selected.get("repo")
    if selected.get("route") != "closeout":
        return {**selected, "ok": True}
    inner = nested.get("result") if isinstance(nested.get("result"), dict) else nested
    failed = inner if inner.get("ok") is False else nested if nested.get("ok") is False else None
    if failed is not None:
        return {
            **selected,
            "ok": True,
            "route": "failed",
            "error": failed.get("error") or "closeout subflow failed",
        }
    out = dict(inner.get("result") or inner)
    return {**out, "ok": True, "slot": slot, "repo": repo}
