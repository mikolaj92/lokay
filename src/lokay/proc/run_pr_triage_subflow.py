"""Launch the authored pr_triage Fala for one selected PR."""

from lokay.graph_run import run_path


def run(target: dict, *, config_path: str | None, live: bool) -> dict:
    try:
        result = run_path(
            path_id="pr_triage",
            repo=str(target["repo"]),
            pr=int(target["pr"]),
            branch=str(target["branch"]),
            config_path=config_path,
            live=live,
        )
    except Exception as exc:
        return {"ok": True, **target, "route": "failed", "error": str(exc)}
    return {"ok": True, **target, "route": "completed", "triage": result}
