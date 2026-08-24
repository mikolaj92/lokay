"""Select one closed localization result from the authored path."""


def terminal(written: dict, candidate: dict) -> dict:
    if written.get("route") == "success":
        return {
            "ok": True,
            "result": {k: v for k, v in written.items() if k not in {"route", "atom"}},
        }
    reason = str(written.get("reason") or candidate.get("reason") or "empty_paths")
    messages = {
        "empty_seed": "localize seed empty: need issue body, approach.md, checks, or seed",
        "invalid_json": "localize agent returned invalid JSON twice",
        "missing_worktree": "worktree not found",
    }
    return {
        "ok": True,
        "result": {
            "ok": False,
            "error": messages.get(
                reason, "localize produced no edit paths; refusing empty scope"
            ),
            "reason": reason,
            "paths": [],
        },
    }
