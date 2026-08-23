"""Select one authored untracked-path slot."""


def select(listed: dict, *, slot: int) -> dict:
    paths = list(listed.get("paths") or [])
    return (
        {
            "ok": True,
            "route": "path",
            "slot": slot,
            "worktree": listed["worktree"],
            "path": paths[slot - 1],
        }
        if 1 <= slot <= len(paths)
        else {"ok": True, "route": "empty", "slot": slot}
    )
