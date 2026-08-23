"""Validate the closed uncommitted/ahead shape before reading commit semantics."""


def validate(changes: dict) -> dict:
    kind = str(changes.get("uncommitted"))
    ahead = int(changes.get("ahead") or 0)
    if kind == "plan_only":
        return {
            **changes,
            "route": "error",
            "error": "cannot resume self-repair worktree with uncommitted plan evidence",
        }
    if kind == "real" and ahead:
        return {
            **changes,
            "route": "error",
            "error": "cannot resume dirty self-repair worktree with unrecognized commits",
        }
    return {
        **changes,
        "route": (
            "commit_facts" if ahead else "ancestry" if kind == "real" else "remove"
        ),
    }
