"""Run only the pure duplicate-delivery intake rule."""

from lokay.intake import check_duplicate_ai_pr
from lokay.models import Issue


def run(issue: dict, parsed: dict) -> dict:
    return {
        "ok": True,
        "route": "selected",
        "check": check_duplicate_ai_pr(
            Issue.from_dict(issue["issue"]), covering_prs=parsed.get("prs") or []
        ).to_dict(),
    }
