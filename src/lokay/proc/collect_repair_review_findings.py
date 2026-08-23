"""Collect the already selected review findings without semantic reinterpretation."""


def collect(review: dict) -> dict:
    return {
        "ok": True,
        "evidence_kind": "review_findings",
        "evidence": {"review": review},
    }
