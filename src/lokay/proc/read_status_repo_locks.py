"""Read repo-lock occupancy without acquiring or unlinking lock files."""

from pathlib import Path

from lokay.proc.repo_lock import inspect_repo_lock


def read(config: dict) -> dict:
    root = Path(config["state_path"]).parent / "repo-locks"
    locks: list[dict] = []
    try:
        paths = sorted(root.glob("*.lock")) if root.is_dir() else []
    except OSError:
        return {"ok": True, "repo_locks": [], "error": "unreadable"}
    for path in paths:
        fact = inspect_repo_lock(path)
        repo = path.name.removesuffix(".lock").replace("__", "/", 1)
        locks.append({"repo": repo, "busy": bool(fact.get("busy")), "path": str(path)})
    return {"ok": True, "repo_locks": locks}
