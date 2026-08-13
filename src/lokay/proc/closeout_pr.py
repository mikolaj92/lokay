"""One job: checks → route → triage/repair/ci-waiting for one open AI PR."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.compose.pr_repair import compose_pr_repair
from lokay.compose.pr_triage import compose_pr_triage
from lokay.envelope import emit_exit, err, ok
from lokay.merge_policy import WAITING_REASONS
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.proc import pr_checks as p_checks
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live
from lokay.proc.pr_route import run_pr_route
from lokay.stuck import clear_issue, issue_number_from_branch, save_stuck

_COUNTERS = (
    "pending_checks",
    "no_checks_blocked",
    "merge_conflicts",
    "needs_repair",
    "mergeable_green",
    "merge_disabled",
    "review_limbo",
)


def _done(
    *,
    repo: str,
    pr_num: int,
    route: str,
    reason: str,
    still_open: bool,
    actions: list[dict[str, Any]],
    repair_budget: int,
    progress: int,
    remaining_closed: int,
    counters: dict[str, int],
) -> dict[str, Any]:
    return ok(
        repo=repo,
        pr=pr_num,
        route=route,
        reason=reason,
        still_open=still_open,
        merged=not still_open,
        actions=actions,
        repair_budget=repair_budget,
        progress=progress,
        remaining_closed=remaining_closed,
        **{key: int(counters.get(key) or 0) for key in _COUNTERS},
    )


def run_closeout_pr(
    *,
    repo: str,
    pr: dict[str, Any],
    config_path: str | None,
    live: bool,
    merge_enabled: bool,
    require_checks: bool,
    repair_budget: int,
    executor_enabled: bool,
    branch_prefix: str,
    stuck: dict[str, Any],
    stuck_path: Path,
) -> dict[str, Any]:
    """Handle one open AI PR. Mutates ``pr`` labels and ``stuck`` as today."""
    actions: list[dict[str, Any]] = []
    counters = {key: 0 for key in _COUNTERS}
    progress = 0
    remaining_closed = 0
    pr_num = int(pr["number"])
    head = str(pr.get("head_ref") or "")
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []

    def done(route: str, reason: str = "", *, still_open: bool = True) -> dict[str, Any]:
        return _done(
            repo=repo,
            pr_num=pr_num,
            route=route,
            reason=reason,
            still_open=still_open,
            actions=actions,
            repair_budget=repair_budget,
            progress=progress,
            remaining_closed=remaining_closed,
            counters=counters,
        )

    if is_manual_pr(pr):
        actions.append(
            {
                "step": "skip_manual_pr",
                "repo": repo,
                "pr": pr_num,
                "reason": "ai:needs-review is terminal/manual",
            }
        )
        return done("skip", "manual")
    # Conflicts are handled by resolve_conflicts (upstream Fala atom).
    if str(pr.get("mergeable") or "").upper() in {"CONFLICTING", "DIRTY"}:
        return done("skip", "conflict")
    chk = run_proc(p_checks.main, [*cfg_flag, "--repo", repo, "--pr", str(pr_num)])
    actions.append({"step": "pr_checks", "pr": pr_num, **chk})
    if not chk.get("ok"):
        return done("skip", "checks_error")
    routed = run_pr_route(
        checks=chk,
        merge_enabled=merge_enabled,
        require_checks=require_checks,
        labels=pr.get("labels"),
    )
    route = str(routed.get("route") or "skip")
    reason = str(routed.get("reason") or "")
    if route == "repair":
        counters["needs_repair"] += 1
        if live and repair_budget > 0 and executor_enabled and head:
            repair = compose_pr_repair(
                config_path=config_path,
                repo=repo,
                pr_number=pr_num,
                branch=head,
                live=True,
            )
            actions.append({"step": "pr_repair", "pr": pr_num, "branch": head, **repair})
            repair_budget -= 1
        return done("repair", reason)
    if route == "wait":
        if reason == "checks_pending":
            counters["pending_checks"] += 1
            issue_n = issue_number_from_branch(head, branch_prefix=branch_prefix)
            if live and issue_n is not None:
                staged = run_proc(
                    p_stage.main,
                    [
                        *cfg_flag,
                        *live_flag,
                        "--repo",
                        repo,
                        "--issue",
                        str(issue_n),
                        "--stage",
                        "ci-waiting",
                    ],
                )
                actions.append(
                    {
                        "step": "stage_ci_waiting",
                        "repo": repo,
                        "issue": issue_n,
                        "pr": pr_num,
                        **staged,
                    }
                )
        elif reason == "checks_none_require_checks":
            counters["no_checks_blocked"] += 1
        elif reason == "merge_disabled":
            counters["mergeable_green"] += 1
            counters["merge_disabled"] += 1
        return done("wait", reason)
    if route != "merge":
        return done(route, reason)
    counters["mergeable_green"] += 1
    if not live or not head:
        return done("merge", reason)
    tri = compose_pr_triage(
        config_path=config_path,
        repo=repo,
        pr_number=pr_num,
        branch=head,
        live=True,
    )
    actions.append({"step": "pr_triage", "pr": pr_num, "branch": head, **tri})
    if not tri.get("ok"):
        return done("merge", reason)
    if tri.get("skipped"):
        tri_reason = str(tri.get("reason") or "")
        if tri.get("waiting") or tri_reason in WAITING_REASONS:
            if tri_reason == "checks_pending":
                counters["pending_checks"] += 1
            elif tri_reason == "checks_none_require_checks":
                counters["no_checks_blocked"] += 1
            elif tri_reason == "merge_disabled":
                counters["merge_disabled"] += 1
            counters["mergeable_green"] = max(0, counters["mergeable_green"] - 1)
        elif tri.get("repairable") or tri_reason == "checks_failed":
            counters["needs_repair"] += 1
            if tri_reason == "checks_failed":
                counters["mergeable_green"] = max(0, counters["mergeable_green"] - 1)
            if repair_budget > 0 and executor_enabled:
                repair = compose_pr_repair(
                    config_path=config_path,
                    repo=repo,
                    pr_number=pr_num,
                    branch=head,
                    live=True,
                    review=dict(tri.get("review") or {}),
                )
                actions.append(
                    {
                        "step": "pr_review_repair",
                        "pr": pr_num,
                        "branch": head,
                        **repair,
                    }
                )
                repair_budget -= 1
        else:
            counters["mergeable_green"] = max(0, counters["mergeable_green"] - 1)
            counters["review_limbo"] += 1
        if tri.get("reason") == "merge_conflicts":
            counters["merge_conflicts"] += 1
        review = tri.get("review")
        if (
            tri.get("escalated")
            or tri.get("needs_review")
            or (
                isinstance(review, dict)
                and (
                    review.get("verdict") == "needs_human"
                    or review.get("secrets") is True
                )
            )
        ):
            pr["labels"] = ["ai:needs-review"]
        return done("merge", tri_reason)
    progress = 1
    remaining_closed = 1
    counters["mergeable_green"] = max(0, counters["mergeable_green"] - 1)
    issue_n = issue_number_from_branch(head, branch_prefix=branch_prefix)
    if issue_n is not None:
        clear_issue(stuck, repo, issue_n)
        save_stuck(stuck_path, stuck)
    return done("merge", reason, still_open=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-closeout-pr")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--mergeable", default="")
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--merge-enabled", action="store_true")
    parser.add_argument("--require-checks", action="store_true")
    parser.add_argument("--repair-budget", type=int, default=0)
    parser.add_argument("--executor-enabled", action="store_true")
    parser.add_argument("--branch-prefix", default="ai/fix/")
    parser.add_argument("--stuck-path", default="")
    args = parser.parse_args(argv)
    if not args.repo:
        return emit_exit(err("repo required"))
    stuck_path = Path(str(args.stuck_path or ""))
    pr = {
        "number": int(args.pr),
        "head_ref": str(args.head_ref or ""),
        "mergeable": str(args.mergeable or ""),
        "labels": list(args.label or []),
    }
    return emit_exit(
        run_closeout_pr(
            repo=str(args.repo),
            pr=pr,
            config_path=args.config,
            live=bool(args.live),
            merge_enabled=bool(args.merge_enabled),
            require_checks=bool(args.require_checks),
            repair_budget=int(args.repair_budget),
            executor_enabled=bool(args.executor_enabled),
            branch_prefix=str(args.branch_prefix or "ai/fix/"),
            stuck={"issues": {}},
            stuck_path=stuck_path,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
