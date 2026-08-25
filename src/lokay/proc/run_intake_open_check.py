"""Run only the pure issue-open intake rule."""

from lokay.intake import check_open


def run(issue: dict) -> dict:
    return {
        "ok": True,
        "route": "selected",
        "check": check_open(state=(issue.get("issue") or {}).get("state")).to_dict(),
    }
