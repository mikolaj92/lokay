"""Invoke the authored one-PR closeout Fala."""

from lokay.graph_run import run_path


def run(*, selected: dict, config_path: str | None, live: bool) -> dict:
    pr = dict(selected.get("pr") or {})
    return run_path(
        path_id="closeout_pr",
        repo=str(selected.get("repo") or ""),
        pr=int(pr.get("number") or 0),
        branch=str(pr.get("head_ref") or ""),
        config_path=config_path,
        live=live,
        max_ticks=64,
        extra_inputs={"selected": selected},
    )
