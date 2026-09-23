"""Read the parent-authorized localization scope."""


def read(worktree: dict) -> dict:
    if worktree.get("route") != "read":
        return {"ok": True, "route": "unused", "paths": []}
    authorized = worktree.get("authorized_paths")
    if not isinstance(authorized, list) or not all(isinstance(x, str) for x in authorized):
        return {
            "ok": True,
            "route": "terminal",
            "reason": "localize_unverified",
            "paths": [],
        }
    return {
        "ok": True,
        "route": "scope",
        "paths": [x.removeprefix("./").rstrip("/") for x in authorized if x.rstrip("/")],
    }
