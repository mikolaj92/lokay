"""Run one issue_sieve_row child. No loop."""

from lokay.graph_run import run_path


def run(
    *,
    listed: dict,
    last: dict | None,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    slot: int,
) -> dict:
    del slot
    return run_path(
        path_id="issue_sieve_row",
        repo="local/issue-sieve-row",
        config_path=config_path,
        live=live,
        extra_inputs={
            "pass_dir": pass_dir,
            "listed": listed,
            "last": last or {},
        },
    )
