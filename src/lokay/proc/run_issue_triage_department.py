"""Parent slot: sieve-only issue_triage_department. Zero code. Zero PR."""

from __future__ import annotations

from lokay.graph_run import run_path


def child_graph(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="issue_triage_department",
        repo="local/issue-triage-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return {
        **child_graph(pass_dir=pass_dir, config_path=config_path, live=live),
        "body": "child",
    }
