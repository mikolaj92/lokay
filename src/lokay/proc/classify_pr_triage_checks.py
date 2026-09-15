"""Classify one PR checks envelope for the pr_triage Fala."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok


def classify(checks: Mapping[str, Any]) -> dict[str, Any]:
    status = str(checks.get("status") or "").strip().lower()
    import re

    candidate = str(checks.get("head_sha") or "").lower()
    head_sha = candidate if re.fullmatch(r"[a-f0-9]{40}", candidate) else ""
    if (
        checks.get("merge_ok") is True
        or checks.get("green") is True
        or status == "passed"
    ):
        return ok(route="review", reason="checks_green", head_sha=head_sha)
    if status == "failed":
        if checks.get("require_checks"):
            if not head_sha:
                return ok(route="wait", reason="ci_repair_start_head_missing", waiting=True, repairable=False, repair_kind="ci")
            return ok(route="repair", reason="checks_failed", repairable=True, repair_kind="ci", head_sha=head_sha)
        return ok(route="review", reason="checks_unstable_not_required", head_sha=head_sha)
    if status == "pending":
        return ok(route="wait", reason="checks_pending", waiting=True, head_sha=head_sha)
    if status == "none":
        if checks.get("require_checks") and not checks.get("merge_ok"):
            return ok(route="wait", reason="checks_none_require_checks", waiting=True, head_sha=head_sha)
        return ok(route="review", reason="checks_none", head_sha=head_sha)
    if status == "offline":
        return ok(route="wait", reason="checks_offline", waiting=True, head_sha=head_sha)
    return ok(route="wait", reason="checks_missing", waiting=True, head_sha=head_sha)


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
