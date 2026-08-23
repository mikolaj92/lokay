"""Purely reduce one repo listing against PR and stuck physical state."""

from lokay.passkit.working import load_begin_working
from lokay.stuck import excluded_numbers, issue_numbers_covered_by_prs


def classify(*, pass_dir: str, selected: dict, listed: dict) -> dict:
    repo = str(selected.get("repo") or listed.get("repo") or "")
    if selected.get("route") != "survey":
        return {
            "ok": True,
            "route": selected.get("route") or "empty",
            "repo": repo,
            "implementable": [],
            "covered": [],
            "blocked": [],
        }
    if listed.get("route") != "listed":
        return {
            "ok": True,
            "route": "failed",
            "repo": repo,
            "implementable": [],
            "covered": [],
            "blocked": [],
        }
    begin, working = load_begin_working(pass_dir)
    covered_numbers = issue_numbers_covered_by_prs(
        list((working.get("prs_by_repo") or {}).get(repo) or []),
        branch_prefix=str(begin.get("branch_prefix") or "ai/fix/"),
    )
    blocked_numbers = excluded_numbers(
        dict(working.get("stuck") or begin.get("stuck") or {}), repo
    )
    issues = list(listed.get("issues") or [])
    covered = [row for row in issues if int(row.get("number", -1)) in covered_numbers]
    blocked = [row for row in issues if int(row.get("number", -1)) in blocked_numbers]
    excluded = covered_numbers | blocked_numbers
    ready = [row for row in issues if int(row.get("number", -1)) not in excluded]
    return {
        "ok": True,
        "route": "blocked" if blocked else "record",
        "repo": repo,
        "implementable": ready,
        "covered": covered,
        "blocked": blocked,
    }
