"""Run one selected issue through the authored semantic triage Fala."""

from lokay.graph_run import run_path


def run(target: dict, *, config_path: str | None) -> dict:
    try:
        result = run_path(
            path_id="issue_triage",
            repo=str(target["repo"]),
            issue=int(target["issue"]),
            config_path=config_path,
            live=True,
        )
    except Exception as exc:
        return {"ok": True, "route": "failed", "error": str(exc), **target}
    return {"ok": True, "route": "completed", "triage": result, **target}
