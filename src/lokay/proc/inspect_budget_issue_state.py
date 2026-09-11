"""Read issue + covering-PR facts for one detached receipt."""

from lokay.passkit.support import run_proc
from lokay.proc import get_issue
from lokay.proc.find_existing_delivery_pr import find as find_covering


def inspect(selected: dict, *, config_path: str | None, live: bool) -> dict:
    if not live:
        return {**selected, "route": "unknown", "closed": False, "covering": False}
    argv = (["--config", config_path] if config_path else []) + [
        "--live",
        "--repo",
        selected["repo"],
        "--issue",
        str(selected["issue"]),
    ]
    out = run_proc(get_issue.main, argv)
    state = str((out.get("issue") or {}).get("state") or "").upper()
    closed = bool(out.get("ok") and state == "CLOSED")
    if closed:
        return {**selected, "route": "closed", "closed": True, "covering": False}
    covering = find_covering(
        {"repo": selected["repo"], "issue": selected["issue"]}, live=live
    )
    pull = covering.get("pull") if covering.get("route") == "existing" else None
    if pull:
        # Coding slot is done. Covering OPEN PR is leftover for pr_triage.
        return {
            **selected,
            "route": "covering",
            "closed": False,
            "covering": True,
            "covering_pr": pull,
        }
    return {
        **selected,
        "route": "open_or_unknown",
        "closed": False,
        "covering": False,
        "covering_probe_failed": covering.get("route") == "terminal",
    }
