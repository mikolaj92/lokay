"""Run only the pure already-satisfied intake rule."""

from pathlib import Path

from lokay.intake import check_satisfied
from lokay.models import Issue


def run(issue: dict, clone: dict) -> dict:
    return {
        "ok": True,
        "route": "selected",
        "check": check_satisfied(
            Issue.from_dict(issue["issue"]),
            clone_path=Path(clone["clone_path"]) if clone.get("clone_path") else None,
        ).to_dict(),
    }
