"""Validate one coding-agent response against the closed schema."""

from __future__ import annotations
from lokay.coding_boundary import validate_output


def validate(stdout: str) -> dict:
    return validate_output(stdout)


def validate_source(source_blob: dict, validate) -> dict:
    """Validate one coding response from its bounded result channel.

    An empty localize and an over-bound result fail closed with a named
    reason; the diagnostic tail is never the result document.
    """
    if str(source_blob.get("route") or "") == "empty" or str(
        source_blob.get("reason") or ""
    ) in {"localize_empty", "localize_missing", "localize_timeout"}:
        return {
            "ok": True,
            "route": "empty",
            "reason": str(source_blob.get("reason") or "localize_empty"),
        }
    if source_blob.get("result_truncated"):
        return {
            "ok": True,
            "route": "fail_closed",
            "decision": {"verdict": "fail_closed"},
            "reason": "coding_result_truncated",
        }
    validated = validate(
        str(
            source_blob.get("result_stdout")
            or source_blob.get("stdout")
            or source_blob.get("stdout_tail")
            or ""
        )
    )
    if validated.get("route") == "valid" and source_blob.get("session"):
        validated["session"] = source_blob["session"]
    return validated
