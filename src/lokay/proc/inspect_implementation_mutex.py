"""Read the repository mutex for one selected implementation candidate."""

from lokay.proc.repo_mutex import inspect_mutex, _live_ps_text


def inspect(candidate: dict) -> dict:
    try:
        mutex = inspect_mutex(repo=str(candidate["repo"]), ps_text=_live_ps_text())
    except Exception as exc:
        return {
            "ok": True,
            "route": "keep",
            "reason": "unknown",
            "error": str(exc),
            **candidate,
        }
    return {
        "ok": True,
        "route": "keep" if mutex.get("busy") else "free",
        "reason": "busy" if mutex.get("busy") else "free",
        "pids": mutex.get("pids") or [],
        **candidate,
    }
