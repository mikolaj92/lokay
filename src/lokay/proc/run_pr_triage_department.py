"""Parent slot: existing prs child (sieve; optional repair stays inside prs)."""

from lokay.proc.prs_subflow import run as run_prs


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_prs(pass_dir=pass_dir, config_path=config_path, live=live)
