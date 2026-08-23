"""Stabilize optional prepare effects into the authored domain result."""


def select(
    checkout: dict,
    gate: dict,
    published: dict,
    base: dict,
    classified: dict,
    removed: dict,
    created: dict,
) -> dict:
    if gate.get("route") == "planned":
        return {
            "ok": True,
            "planned": True,
            "worktree": checkout["worktree"],
            "base_sha": "",
        }
    if published.get("route") == "published":
        return {
            "ok": True,
            "planned": False,
            "repo": checkout["repo"],
            "worktree": "",
            "base_sha": published["commit"],
            "commit": published["commit"],
            "already_on_main": True,
        }
    if classified.get("route") == "error":
        return {"ok": False, "error": classified.get("error")}
    if removed.get("route") == "remove_failed":
        return {"ok": False, "error": removed.get("error")}
    if classified.get("route") == "resume":
        return {
            "ok": True,
            "planned": False,
            "repo": checkout["repo"],
            "worktree": checkout["worktree"],
            "base_sha": base["base_sha"],
            "resumed": True,
            "candidate_commit": classified.get("candidate_commit", ""),
        }
    if created.get("route") == "created":
        return {
            "ok": True,
            "planned": False,
            "repo": checkout["repo"],
            "worktree": checkout["worktree"],
            "base_sha": base["base_sha"],
        }
    return {"ok": False, "error": "self-repair prepare path incomplete"}
