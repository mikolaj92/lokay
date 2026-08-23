"""Stabilize one authored closeout slot and its nested result."""


def record(selected: dict, nested: dict) -> dict:
    if selected.get("route") != "closeout":
        return selected
    if not nested.get("ok"):
        return {
            **selected,
            "route": "failed",
            "error": nested.get("error") or "closeout subflow failed",
        }
    out = dict(nested.get("result") or nested)
    return {**out, "slot": selected.get("slot"), "repo": selected.get("repo")}
