"""Run the authored PR review/merge Fala for one PR."""

from lokay.compose.pr_triage import compose_pr_triage


def run(target: dict, *, config_path: str | None, live: bool) -> dict:
    if target.get("route") != "pr" or not target.get("branch"):
        return {"ok": True, "route": "skip", **target}
    result = compose_pr_triage(
        config_path=config_path,
        repo=str(target["repo"]),
        pr_number=int(target["pr"]),
        branch=str(target["branch"]),
        live=live,
    )
    return {"ok": True, "route": "completed", "triage": result, **target}
