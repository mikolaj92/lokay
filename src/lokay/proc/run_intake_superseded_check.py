"""Run only the pure superseded intake rule."""

from lokay.intake import check_superseded
from lokay.models import Issue


def run(request: dict, issue: dict) -> dict:
    return {
        "ok": True,
        "route": "selected",
        "check": check_superseded(
            Issue.from_dict(issue["issue"]),
            merged_prs=request.get("merged_prs") or [],
            closed_tracker_done=bool(request.get("tracker_done")),
        ).to_dict(),
    }
