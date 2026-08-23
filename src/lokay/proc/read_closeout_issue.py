"""Read the bound issue state for one PR, when a binding exists."""

from lokay.passkit.support import run_proc
from lokay.proc import get_issue


def read(inspected: dict, *, config_path: str | None) -> dict:
    issue = inspected.get("issue")
    if issue is None:
        return {"ok": True, "route": "unbound", "state": ""}
    argv = (["--config", config_path] if config_path else []) + [
        "--repo",
        inspected["repo"],
        "--issue",
        str(issue),
        "--live",
    ]
    out = run_proc(get_issue.main, argv)
    state = str((out.get("issue") or {}).get("state") or "").upper()
    return {
        "ok": True,
        "route": "closed" if out.get("ok") and state != "OPEN" else "open_or_unknown",
        "state": state,
        "issue": issue,
        "read": out,
    }
