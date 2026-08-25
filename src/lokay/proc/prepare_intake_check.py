"""Normalize one bounded mechanical intake-check request."""

TARGET = "mikolaj92/lokay"


def prepare(
    *,
    repo: str,
    issue: int,
    check: str,
    merged_prs: list[int],
    tracker_done: bool,
    covering_prs: list[str],
    live: bool,
) -> dict:
    return {
        "ok": True,
        "route": "read" if repo == TARGET else "terminal",
        "reason": "" if repo == TARGET else "repo_not_intake_target",
        "repo": repo,
        "issue": issue,
        "check": check,
        "merged_prs": merged_prs,
        "tracker_done": tracker_done,
        "covering_prs": covering_prs,
        "live": live,
    }
