"""Parent slot: existing issues child when the sieve did not already conduct it."""

from lokay.envelope import ok
from lokay.proc.issues_subflow import run as run_issues


def run(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage_ran: bool,
) -> dict:
    if triage_ran:
        return ok(route="already_conducted", department="executor")
    return run_issues(pass_dir=pass_dir, config_path=config_path, live=live)
