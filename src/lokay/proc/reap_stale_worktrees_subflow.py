"""Invoke the authored bounded stale-worktree hygiene Fala."""

from lokay.graph_run import run_path
from lokay.proc.classify_stale_worktree_reap import classify


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    """Run the cleanup child. Throw / empty / not-ok is a classified route."""
    try:
        out = run_path(
            path_id="stale_worktree_reap",
            repo="local/worktrees",
            config_path=config_path,
            live=live,
            extra_inputs={"pass_dir": pass_dir},
        )
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return classify(error=exc)
    return classify(out)
