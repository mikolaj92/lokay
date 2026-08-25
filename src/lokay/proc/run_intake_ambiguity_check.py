"""Run only the pure ambiguity intake rule."""

from lokay.intake import check_ambiguity
from lokay.models import Issue


def run(issue: dict) -> dict:
    return {
        "ok": True,
        "route": "selected",
        "check": check_ambiguity(Issue.from_dict(issue["issue"])).to_dict(),
    }
