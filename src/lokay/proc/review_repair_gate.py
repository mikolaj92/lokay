"""Classify one request_changes result for repair or terminal manual handling."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok


def route_review_repair(review: Mapping[str, Any]) -> dict[str, Any]:
    decision = review.get("decision")
    if not isinstance(decision, Mapping):
        return err("review decision required")
    if decision.get("verdict") != "request_changes":
        return ok(route="not_applicable", reason="review_does_not_request_changes")
    if review.get("escalated") or decision.get("secrets") is True:
        return ok(route="needs_human", reason="review_repair_escalated")
    return ok(route="repair", reason="review_requested_changes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-review-repair-gate")
    parser.add_argument("--review-json", required=True)
    args = parser.parse_args(argv)
    try:
        review = json.loads(args.review_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid review JSON: {exc}"))
    if not isinstance(review, dict):
        return emit_exit(err("review JSON object required"))
    return emit_exit(route_review_repair(review))


if __name__ == "__main__":
    raise SystemExit(main())
