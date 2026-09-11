"""Read GitHub state for one live receipt: closed, covering PR, or occupied."""

from lokay.passkit.support import run_proc
from lokay.proc import get_issue
from lokay.proc.find_existing_delivery_pr import find as find_covering


def inspect(selected: dict, *, config_path: str | None, live: bool) -> dict:
    row = dict(selected["receipt"])
    repo = str(row.get("repo") or "")
    issue = int(row["issue"])
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", repo, "--issue", str(issue)]
    )
    viewed = run_proc(get_issue.main, argv)
    state = str((viewed.get("issue") or {}).get("state") or "").upper()
    closed = bool(viewed.get("ok") and state and state != "OPEN")
    if closed:
        return {
            "ok": True,
            "route": "closed",
            "repo": repo,
            "issue": issue,
            "receipt": row,
            "viewed": viewed,
        }
    covering = find_covering({"repo": repo, "issue": issue}, live=live)
    pull = covering.get("pull") if covering.get("route") == "existing" else None
    if pull:
        # Coding slot is done. Covering OPEN PR is leftover for pr_triage.
        return {
            "ok": True,
            "route": "covering",
            "repo": repo,
            "issue": issue,
            "receipt": row,
            "viewed": viewed,
            "covering_pr": pull,
        }
    return {
        "ok": True,
        "route": "occupied",
        "repo": repo,
        "issue": issue,
        "receipt": row,
        "viewed": viewed,
        "covering_probe_failed": covering.get("route") == "terminal",
    }
