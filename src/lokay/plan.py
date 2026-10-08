"""Tick plan over a snapshot. Not wired into a node yet."""
from lokay.owner_commands import owner_command


def plan(snapshot, *, slots=1):
    candidates = []
    for repo, body in snapshot.get("repos", {}).items():
        for issue in body.get("issues", []):
            if owner_command("\n".join(issue.get("owner_commands") or [])) == "skip":
                continue
            candidates.append({
                "work_id": f"{repo}#{issue['number']}",
                "kind": "build",
                "mode": "build",
                "repo": repo,
            })
    return {"candidates": candidates, "free_slots": slots, "wip": {}, "backoff": {}}
