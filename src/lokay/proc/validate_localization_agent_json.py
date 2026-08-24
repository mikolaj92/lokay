"""Validate one localization-agent JSON object without choosing fallback semantics."""

from lokay.localize_agent import LocalizeAgentError, parse_localize_output
from lokay.pr_review import PrReviewError


def validate(attempt: dict) -> dict:
    if attempt.get("route") != "validate":
        return {"ok": True, "route": "unused"}
    try:
        paths = parse_localize_output(str(attempt.get("text") or ""))
    except (LocalizeAgentError, PrReviewError) as exc:
        return {"ok": True, "route": "invalid", "validator_error": str(exc)}
    return {"ok": True, "route": "valid", "paths": paths}
