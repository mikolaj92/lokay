"""Invoke the authored ready-survey Fala with its own journal."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="survey_ready",
        repo="local/ready-survey",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )
