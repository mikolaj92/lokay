"""Parent slot: sieve-only issue_triage_department. Zero code. Zero PR."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="issue_triage_department",
        repo="local/issue-triage-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )
