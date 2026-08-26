"""Run the authored PR review/repair/merge Fala for one PR."""

from lokay.compose.pr_triage import compose_pr_triage


def run(target: dict, *, config_path: str | None, live: bool) -> dict:
    if target.get("route") != "pr" or not target.get("branch"):
        return {"ok": True, **target, "route": "skip"}
    try:
        result = compose_pr_triage(
            config_path=config_path,
            repo=str(target["repo"]),
            pr_number=int(target["pr"]),
            branch=str(target["branch"]),
            live=live,
        )
    except Exception as exc:
        return {"ok": True, **target, "route": "failed", "error": str(exc)}
    return {"ok": True, **target, "route": "completed", "triage": result}
