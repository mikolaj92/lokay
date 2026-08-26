"""Parent boundary: run the PRs child Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="prs",
        repo="local/prs",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
    )
