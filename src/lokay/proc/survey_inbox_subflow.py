"""Invoke the authored catalog inbox-survey Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="survey_inbox",
        repo="local/inbox-survey",
        config_path=config_path,
        live=live,
        max_ticks=512,
        extra_inputs={"pass_dir": pass_dir},
    )
