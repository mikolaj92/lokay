"""Collect complete covering-AI-PR evidence for one issue."""

from __future__ import annotations
from lokay.intake_io import covering_ai_prs


def collect(*, runner, repo: str, issue: int, branch_prefix: str, live: bool) -> dict:
    try:
        rows = covering_ai_prs(
            runner, repo, issue, branch_prefix=branch_prefix, live=live
        )
    except Exception as exc:
        return {
            "ok": True,
            "collected": False,
            "reason": str(exc),
            "probe_failed": True,
            "covering_prs": [],
        }
    return {
        "ok": True,
        "collected": True,
        "covering_prs": rows,
        "additional_evidence": {"covering_prs": rows},
    }
