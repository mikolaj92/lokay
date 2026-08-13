"""One job: fail-closed closeout route from checks JSON.

Emits ``wait`` | ``repair`` | ``merge`` | ``skip``. Reuses
``merge_policy.decide_auto_merge`` (no second matrix). No GitHub, git, Fala,
or tests runner.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.merge_policy import decide_auto_merge

_ACTION_TO_ROUTE = {
    "merge": "merge",
    "waiting": "wait",
    "repair": "repair",
    "blocked": "skip",
    "disabled": "wait",
}


def run_pr_route(
    *,
    checks: Mapping[str, Any] | None,
    merge_enabled: bool,
    require_checks: bool = False,
    labels: Any = None,
) -> dict[str, Any]:
    """Classify one PR from checks + merge/require flags + optional labels."""
    if not isinstance(checks, Mapping):
        return err("checks JSON object required")
    # Checks/labels first so pending still waits (ci-waiting) when merge is off.
    gate = decide_auto_merge(
        merge_enabled=True,
        require_checks=bool(require_checks),
        require_llm_review=False,
        checks=checks,
        pr_labels=labels,
    )
    if not merge_enabled and gate.action == "merge":
        gate = decide_auto_merge(merge_enabled=False, checks=checks, pr_labels=labels)
    route = _ACTION_TO_ROUTE.get(gate.action, "skip")
    return ok(
        route=route,
        reason=gate.reason,
        waiting=gate.waiting,
        repairable=gate.repairable,
        needs_review=gate.needs_review,
        merge_ok=gate.merge_ok,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-pr-route")
    parser.add_argument("--checks", default="", help="checks JSON object")
    parser.add_argument("--merge-enabled", action="store_true")
    parser.add_argument("--require-checks", action="store_true")
    parser.add_argument("--label", action="append", default=[])
    args = parser.parse_args(argv)
    raw: Any
    if args.checks:
        try:
            raw = json.loads(args.checks)
        except json.JSONDecodeError:
            return emit_exit(err("checks must be JSON object"))
    else:
        raw = read_stdin_json()
    if not isinstance(raw, dict):
        return emit_exit(err("checks JSON object required"))
    wrapped = not args.checks and "checks" in raw
    checks = raw.get("checks") if wrapped else raw
    labels = list(args.label) if args.label else (raw.get("labels") if wrapped else None)
    merge_enabled = bool(args.merge_enabled) or (wrapped and bool(raw.get("merge_enabled")))
    require_checks = bool(args.require_checks) or (
        wrapped and bool(raw.get("require_checks"))
    )
    return emit_exit(
        run_pr_route(
            checks=checks if isinstance(checks, dict) else None,
            merge_enabled=merge_enabled,
            require_checks=require_checks,
            labels=labels,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
