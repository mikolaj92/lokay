"""Invoke the authored local-test execution Fala."""

from lokay.graph_run import run_path


def run(*, worktree: str, changed_scope: bool) -> dict:
    return run_path(
        path_id="test_local_execution",
        repo="local/test",
        live=False,
        max_ticks=64,
        extra_inputs={"worktree": worktree, "changed_scope": changed_scope},
    )
