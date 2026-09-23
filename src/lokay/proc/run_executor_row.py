"""Run one executor_row child. No loop."""

from lokay.graph_run import run_path


def run(
    *,
    listed: dict,
    last: dict | None,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    slot: int,
    budget: int | None = None,
) -> dict:
    del slot
    extra = {
        "pass_dir": pass_dir,
        "listed": listed,
        "last": last or {},
    }
    if budget is not None:
        extra["budget"] = budget
    return run_path(
        path_id="executor_row",
        repo="local/executor-row",
        config_path=config_path,
        live=live,
        extra_inputs=extra,
    )
