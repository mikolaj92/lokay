"""Remove ready eligibility from one terminated plan-only issue."""

from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park


def park(recorded: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + ["--repo", recorded["repo"], "--issue", str(recorded["issue"])]
    )
    out = run_proc(unbounded_park.main, argv)
    return {**recorded, "route": "reaped", "park": out}
