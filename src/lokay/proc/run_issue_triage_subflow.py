"""Run one selected issue through the authored semantic triage Fala."""

from lokay.graph_run import run_path


def invoke(target: dict, *, config_path: str | None) -> dict:
    result = run_path(
        path_id="issue_triage",
        repo=str(target["repo"]),
        issue=int(target["issue"]),
        config_path=config_path,
        live=True,
    )
    return {**target, "ok": True, "route": "completed", "triage": result}


def failed(target: dict, exc: BaseException) -> dict:
    error = str(exc).strip() or type(exc).__name__
    return {**target, "ok": True, "route": "failed", "error": error}


def run(target: dict, *, config_path: str | None) -> dict:
    try:
        return invoke(target, config_path=config_path)
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        return failed(target, exc)
