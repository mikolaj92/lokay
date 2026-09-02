"""Read the repository lock for one selected implementation candidate."""

from lokay.proc.repo_lock import inspect_repo_lock, repo_lock_dir, repo_lock_path


def inspect(candidate: dict, config_path: str | None = None) -> dict:
    try:
        repo = str(candidate["repo"])
        path = repo_lock_path(repo_lock_dir(config_path).parent, repo)
        fact = inspect_repo_lock(path)
    except Exception as exc:
        return {
            **candidate,
            "ok": True,
            "route": "keep",
            "reason": "unknown",
            "error": str(exc),
        }
    busy = bool(fact.get("busy")) or fact.get("reason") == "unknown"
    return {
        **candidate,
        "ok": True,
        "route": "keep" if busy else "free",
        "reason": "busy" if busy else "free",
        "lock": str(path),
    }
