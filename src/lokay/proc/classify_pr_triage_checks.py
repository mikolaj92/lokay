"""Classify one PR checks envelope for the pr_triage Fala."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok


def classify(checks: Mapping[str, Any]) -> dict[str, Any]:
    status = str(checks.get("status") or "").strip().lower()
    if (
        checks.get("merge_ok") is True
        or checks.get("green") is True
        or status == "passed"
    ):
        return ok(route="review", reason="checks_green")
    if status == "failed":
        return ok(route="repair", reason="checks_failed", repairable=True)
    if status == "pending":
        return ok(route="wait", reason="checks_pending", waiting=True)
    if status == "none":
        if checks.get("require_checks") and not checks.get("merge_ok"):
            return ok(route="wait", reason="checks_none_require_checks", waiting=True)
        return ok(route="review", reason="checks_none")
    if status == "offline":
        return ok(route="wait", reason="checks_offline", waiting=True)
    return ok(route="wait", reason="checks_missing", waiting=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-classify-pr-triage-checks")
    parser.add_argument("--checks-json", required=True)
    args = parser.parse_args(argv)
    try:
        checks = json.loads(args.checks_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid checks JSON: {exc}"))
    if not isinstance(checks, dict):
        return emit_exit(err("checks JSON object required"))
    return emit_exit(classify(checks))


if __name__ == "__main__":
    raise SystemExit(main())
