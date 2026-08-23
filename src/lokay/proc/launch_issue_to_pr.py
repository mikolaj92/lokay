"""Launch one detached issue-to-PR worker after all Fala gates pass."""

from lokay.proc.detach_issue_to_pr import detach_issue_to_pr


def launch(candidate: dict, *, config_path: str | None) -> dict:
    result = detach_issue_to_pr(
        repo=str(candidate["repo"]),
        issue=int(candidate["issue"]),
        config_path=config_path,
    )
    return {
        "ok": True,
        "route": "started" if result.get("ok") else "failed",
        "launch": result,
        **candidate,
    }
