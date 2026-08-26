"""Reduce checks, review-repair, and local-test facts to one pr_triage route."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok


def _skipped(row: Mapping[str, Any]) -> bool:
    if not row:
        return True
    return str(row.get("reason") or "") == "condition_not_met"


def select(
    checks_route: Mapping[str, Any],
    review_gate: Mapping[str, Any],
    test: Mapping[str, Any],
) -> dict[str, Any]:
    cr = str(checks_route.get("route") or "")
    if cr == "wait":
        return ok(
            route="wait",
            reason=str(checks_route.get("reason") or "checks_pending"),
            waiting=True,
        )
    if cr == "repair":
        return ok(
            route="repair",
            reason=str(checks_route.get("reason") or "checks_failed"),
            repairable=True,
        )
    rg = str(review_gate.get("route") or "")
    if rg == "needs_human":
        return ok(
            route="needs_human",
            reason=str(review_gate.get("reason") or "review_repair_escalated"),
        )
    if rg == "repair":
        return ok(
            route="repair",
            reason=str(review_gate.get("reason") or "review_requested_changes"),
            repairable=True,
        )
    if not _skipped(test):
        if test.get("recorded_red") is True or test.get("passed") is False:
            return ok(route="repair", reason="test_local_failed", repairable=True)
        return ok(route="merge", reason="approve_green")
    return ok(route="none", reason="no_merge_path")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-select-pr-triage-outcome")
    parser.add_argument("--checks-json", required=True)
    parser.add_argument("--review-gate-json", required=True)
    parser.add_argument("--test-json", required=True)
    args = parser.parse_args(argv)
    try:
        checks_route = json.loads(args.checks_json)
        review_gate = json.loads(args.review_gate_json)
        test = json.loads(args.test_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid JSON: {exc}"))
    if not all(isinstance(item, dict) for item in (checks_route, review_gate, test)):
        return emit_exit(err("JSON objects required"))
    return emit_exit(select(checks_route, review_gate, test))


if __name__ == "__main__":
    raise SystemExit(main())
