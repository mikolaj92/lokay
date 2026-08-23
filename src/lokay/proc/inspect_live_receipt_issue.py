"""Read the physical GitHub issue state for one live receipt."""

from lokay.passkit.support import run_proc
from lokay.proc import get_issue


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
    return {
        "ok": True,
        "route": "closed" if closed else "occupied",
        "repo": repo,
        "issue": issue,
        "receipt": row,
        "viewed": viewed,
    }
