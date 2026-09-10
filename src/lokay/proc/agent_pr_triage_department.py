"""Live parent slot: pr_triage agent with authored child Fala fallback."""

from __future__ import annotations

from lokay.proc.run_pr_triage_department import run as run_slot


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_slot(pass_dir=pass_dir, config_path=config_path, live=live)
