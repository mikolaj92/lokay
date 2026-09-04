"""Perform one bounded CLOSED-issue probe for one selected repository."""

from lokay.child_harvest import _github_closed_lokay_issues


def probe(selected: dict) -> dict:
    return {
        "ok": True,
        "repo": selected["harvest_repo"],
        "closed": sorted(_github_closed_lokay_issues(selected["harvest_repo"])),
    }
