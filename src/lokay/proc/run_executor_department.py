"""Parent slot: executor_department. Code and PR. Not sieve. Not merge."""

from __future__ import annotations

from lokay.graph_run import run_path


def child_graph(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage: dict | None = None,
) -> dict:
    return run_path(
        path_id="executor_department",
        repo="local/executor-department",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir, "triage": triage or {}},
    )


def run(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage_ran: bool = False,
    triage: dict | None = None,
) -> dict:
    del triage_ran  # sieve is a sibling department; this slot always codes
    return {
        **child_graph(
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
            triage=triage,
        ),
        "body": "child",
    }
