"""List open AI PRs for one selected repository."""

from lokay.passkit.support import run_proc
from lokay.proc import list_prs


def fetch(inspected: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", str(inspected["repo"])]
    )
    result = run_proc(list_prs.main, argv)
    return {
        **inspected,
        "ok": True,
        "route": "listed" if result.get("ok") else "failed",
        "listed": result,
    }
