"""Return the authored self-repair validation terminal result."""


def summarize(rechecked: dict) -> dict:
    if not rechecked.get("ok"):
        return rechecked
    result = {
        "ok": True,
        "validated": True,
        "commit": rechecked.get("validated_commit", ""),
        "worktree": rechecked["worktree"],
        "tests": "uv run --extra dev pytest -q",
    }
    return {"ok": True, "result": result}
