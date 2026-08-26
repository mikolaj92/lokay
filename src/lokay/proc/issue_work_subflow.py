"""Invoke the authored issue-work Fala (step 4): triage, then implement or next row."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    out = run_path(
        path_id="issue_work",
        repo="local/issue-work",
        config_path=config_path,
        live=live,
        extra_inputs={"pass_dir": pass_dir},
        max_ticks=32,
    )
    if not out.get("ok"):
        return {**out, "ok": True, "pass_dir": pass_dir, "issue_work_failed": True}
    return {**out, "pass_dir": pass_dir}
