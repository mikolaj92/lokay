"""Run the leftover delivered-issue closeout effect after one factory pass."""

from lokay.proc.closeout import run_closeout_leftover


def run(*, config_path: str | None, live: bool) -> dict:
    return run_closeout_leftover(config_path=config_path, live=live)
