"""Parent slot: existing issues child (sito). Launch is gated inside issue_row."""

from lokay.proc.issues_subflow import run as run_issues


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_issues(pass_dir=pass_dir, config_path=config_path, live=live)
