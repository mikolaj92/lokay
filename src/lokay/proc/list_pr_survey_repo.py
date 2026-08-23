"""List physical open AI PRs for one repository."""

from lokay.passkit.support import run_proc
from lokay.proc import list_prs


def fetch(selected: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", selected["repo"]]
    )
    out = run_proc(list_prs.main, argv)
    return {
        **selected,
        "ok": True,
        "route": "listed" if out.get("ok") else "failed",
        "prs": list(out.get("prs") or []),
        "listed": out,
    }
