"""Atomic: interpret a GitHub wake reason and run the matching bounded path.

One job: route issue / PR / checks / factory wakes to ``issue_triage``,
``pr_triage``, or ``lokay-mill --max-passes 1``. Prefer invocation from a
self-hosted Actions runner on the mill host (see docs/AUTONOMY.md).
"""

from __future__ import annotations

import argparse
from typing import Any, Callable

from lokay.compose.mill import compose_mill
from lokay.compose.pr_triage import compose_pr_triage
from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live, load_cfg
from lokay.wake import WakePlan, route_wake


_REPO_SKIP_REASON = "repo_not_delivered_by_mini_mill"


def _repo_skip(repo: str, *, planned: bool, plan_only: bool = False) -> dict[str, Any]:
    return ok(
        kind="wake",
        planned=planned,
        plan_only=plan_only,
        skipped=True,
        path=None,
        reason=_REPO_SKIP_REASON,
        repo=repo,
    )


def _parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def execute_wake(
    plan: WakePlan,
    *,
    config_path: str | None,
    live: bool,
    runners: dict[str, Callable[..., dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Invoke the path chosen by ``route_wake`` (injectable for tests)."""
    if plan.skip or not plan.path:
        return ok(
            kind="wake",
            planned=not live,
            skipped=True,
            **plan.as_dict(),
        )

    fns = runners or {}
    if plan.path == "issue_triage":
        run = fns.get("issue_triage") or (
            lambda: run_path(
                path_id="issue_triage",
                repo=str(plan.repo),
                issue=int(plan.issue or 0),
                config_path=config_path,
                live=live,
            )
        )
        result = run()
    elif plan.path == "pr_triage":
        run = fns.get("pr_triage") or (
            lambda: compose_pr_triage(
                config_path=config_path,
                repo=str(plan.repo),
                pr_number=int(plan.pr or 0),
                branch=str(plan.branch or ""),
                live=live,
            )
        )
        result = run()
    elif plan.path == "factory_pass":
        max_passes = int(plan.max_passes or 1)
        run = fns.get("factory_pass") or (
            lambda: compose_mill(
                config_path=config_path,
                live=live,
                max_passes=max_passes,
            )
        )
        result = run()
    else:
        return err("unsupported wake path", **plan.as_dict())

    if not isinstance(result, dict):
        return err("wake path returned non-object", path=plan.path)
    envelope = ok(
        kind="wake",
        planned=not live,
        skipped=False,
        wake_path=plan.path,
        reason=plan.reason,
        repo=plan.repo,
        issue=plan.issue,
        pr=plan.pr,
        branch=plan.branch,
        max_passes=plan.max_passes,
        result=result,
    )
    if not result.get("ok", False):
        return err(
            str(result.get("error") or "wake path failed"),
            kind="wake",
            planned=not live,
            skipped=False,
            wake_path=plan.path,
            reason=plan.reason,
            repo=plan.repo,
            issue=plan.issue,
            pr=plan.pr,
            branch=plan.branch,
            max_passes=plan.max_passes,
            result=result,
        )
    return envelope


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-wake")
    add_config_live(p)
    p.add_argument(
        "--reason",
        required=True,
        help="wake reason: issue_opened | issue_labeled | checks | pr | factory | …",
    )
    p.add_argument("--repo", help="owner/name for issue_triage / pr_triage")
    p.add_argument("--issue", type=int, help="issue number")
    p.add_argument("--pr", type=int, help="PR number")
    p.add_argument("--branch", help="PR head branch (for pr_triage)")
    p.add_argument(
        "--label",
        dest="label_name",
        default="",
        help="label that triggered a labeled event (filter via WAKE_ON_LABELS)",
    )
    p.add_argument(
        "--labels",
        default="",
        help="comma-separated issue labels (spam filter)",
    )
    p.add_argument(
        "--plan-only",
        action="store_true",
        help="emit routing plan JSON only (no Fala/mill invoke)",
    )
    args = p.parse_args(argv)

    repo = str(args.repo or "").strip()

    plan = route_wake(
        reason=str(args.reason),
        repo=args.repo,
        issue=args.issue,
        pr=args.pr,
        branch=args.branch,
        labels=_parse_labels(args.labels),
        label_name=str(args.label_name or "").strip() or None,
    )

    if args.plan_only:
        return emit_exit(
            ok(
                kind="wake",
                planned=True,
                plan_only=True,
                skipped=bool(plan.skip),
                **plan.as_dict(),
            )
        )

    # Validate config early for non-skip executes (dry-run still loads config).
    if not plan.skip:
        try:
            load_cfg(args)
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc), **plan.as_dict()))

    try:
        return emit_exit(
            execute_wake(plan, config_path=args.config, live=bool(args.live))
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), kind="wake", **plan.as_dict()))


if __name__ == "__main__":
    raise SystemExit(main())
