"""Run only the pure issue/repository-shape intake rule."""

from lokay.intake import RepoShape, check_shape
from lokay.models import Issue


def run(issue: dict, shape: dict) -> dict:
    raw = shape["shape"]
    return {
        "ok": True,
        "route": "selected",
        "check": check_shape(
            Issue.from_dict(issue["issue"]),
            RepoShape(kind=raw["kind"], signals=tuple(raw.get("signals") or [])),
        ).to_dict(),
    }
