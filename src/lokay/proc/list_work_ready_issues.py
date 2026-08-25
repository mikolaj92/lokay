"""List open catalog issues for one repository. Mill labels are not a gate."""

from lokay.passkit.support import run_proc
from lokay.proc import list_issues


def fetch(selected: dict, *, config_path: str | None, live: bool) -> dict:
    repo = str(selected["repo"])
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", repo]
    )
    listed = run_proc(list_issues.main, argv)
    return {
        "ok": True,
        "route": "listed" if listed.get("ok") else "failed",
        "repo": repo,
        "issues": list(listed.get("issues") or []),
        "listed": listed,
    }
