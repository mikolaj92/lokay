"""Restore one stale ledger issue to the physical ready stage."""

from lokay.passkit.support import run_proc
from lokay.proc import stage_label


def restore(selected: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            selected["repo"],
            "--issue",
            str(selected["issue"]),
            "--stage",
            "ready",
        ]
    )
    staged = run_proc(stage_label.main, argv)
    return {**selected, "ok": True, "route": "applied", "staged": staged}
