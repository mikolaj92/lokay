"""Create one PR for a committed and pushed over-budget diff."""

from lokay.passkit.support import run_proc
from lokay.proc import pr_create


def create(pushed: dict, *, config_path: str | None, live: bool) -> dict:
    repo = pushed["repo"]
    issue = int(pushed["issue"])
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            repo,
            "--issue",
            str(issue),
            "--title",
            f"fix: {repo}#{issue}",
            "--head",
            pushed["branch"],
            "--body",
            f"Harvested over-budget real diff for {repo}#{issue}.",
        ]
    )
    out = run_proc(pr_create.main, argv)
    return {
        **pushed,
        "route": "harvested" if out.get("ok") and out.get("pr") else "pr_failed",
        "pr": out.get("pr"),
        "created": out,
    }
