"""Read authoritative issue state for one detached receipt."""

from lokay.passkit.support import run_proc
from lokay.proc import get_issue


def inspect(selected: dict, *, config_path: str | None, live: bool) -> dict:
    if not live:
        return {**selected, "route": "unknown", "closed": False}
    argv = (["--config", config_path] if config_path else []) + [
        "--live",
        "--repo",
        selected["repo"],
        "--issue",
        str(selected["issue"]),
    ]
    out = run_proc(get_issue.main, argv)
    state = str((out.get("issue") or {}).get("state") or "").upper()
    return {
        **selected,
        "route": "closed" if out.get("ok") and state == "CLOSED" else "open_or_unknown",
        "closed": bool(out.get("ok") and state == "CLOSED"),
    }
