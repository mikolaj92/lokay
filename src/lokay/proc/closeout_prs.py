"""One job: checks / repair / merge / wait for remaining open AI PRs."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose.pr_repair import compose_pr_repair
from lokay.compose.pr_triage import compose_pr_triage
from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.passkit.working import (
    load_begin_working,
    recount_prs,
    save_begin_working,
    stuck_path_of,
)
from lokay.proc import pr_checks as p_checks
from lokay.proc._common import add_config_live
from lokay.stuck import clear_issue, issue_number_from_branch, save_stuck


def run_closeout_prs(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or {})
    stuck_path = stuck_path_of(begin)
    branch_prefix = str(begin.get("branch_prefix") or "ai/fix/")
    repair_budget = int(begin.get("repair_budget") or 0)
    executor_enabled = bool(begin.get("executor_enabled"))
    merge_enabled = bool(begin.get("merge_enabled"))
    require_checks = bool(begin.get("require_checks"))

    prs_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("prs_by_repo") or {}).items()
    }
    remaining_prs = int(working.get("remaining_prs") or 0)
    pending_checks = int(working.get("pending_checks") or 0)
    no_checks_blocked = int(working.get("no_checks_blocked") or 0)
    merge_conflicts = int(working.get("merge_conflicts") or 0)
    needs_repair = int(working.get("needs_repair") or 0)
    mergeable_green = int(working.get("mergeable_green") or 0)
    review_limbo = int(working.get("review_limbo") or 0)

    for repo_name in list(begin.get("repos") or []):
        pr_list = list(prs_by_repo.get(repo_name) or [])
        still_open: list[dict[str, Any]] = []
        for pr in pr_list:
            if is_manual_pr(pr):
                still_open.append(pr)
                actions.append(
                    {
                        "step": "skip_manual_pr",
                        "repo": repo_name,
                        "pr": int(pr["number"]),
                        "reason": "ai:needs-review is terminal/manual",
                    }
                )
                continue
            pr_num = int(pr["number"])
            head = str(pr.get("head_ref") or "")
            # Conflicts are handled by resolve_conflicts (upstream Fala atom).
            mergeable = str(pr.get("mergeable") or "").upper()
            if mergeable in {"CONFLICTING", "DIRTY"}:
                still_open.append(pr)
                continue
            chk = run_proc(
                p_checks.main,
                [*cfg_flag, "--repo", repo_name, "--pr", str(pr_num)],
            )
            actions.append({"step": "pr_checks", "pr": pr_num, **chk})
            if not chk.get("ok"):
                still_open.append(pr)
                continue
            status = str(chk.get("status") or ("passed" if chk.get("green") else "failed"))
            if status == "failed":
                needs_repair += 1
                if live and repair_budget > 0 and executor_enabled and head:
                    repair = compose_pr_repair(
                        config_path=config_path,
                        repo=repo_name,
                        pr_number=pr_num,
                        branch=head,
                        live=True,
                    )
                    actions.append(
                        {"step": "pr_repair", "pr": pr_num, "branch": head, **repair}
                    )
                    repair_budget -= 1
                still_open.append(pr)
                continue
            if status == "pending":
                pending_checks += 1
                still_open.append(pr)
                continue
            if status == "none":
                if require_checks:
                    no_checks_blocked += 1
                    still_open.append(pr)
                    continue
            elif status not in {"passed", "offline"} and not chk.get("merge_ok"):
                still_open.append(pr)
                continue
            can_merge = bool(chk.get("merge_ok")) or status == "passed" or (
                status == "none" and not require_checks
            )
            if not can_merge:
                still_open.append(pr)
                continue
            if not merge_enabled:
                mergeable_green += 1
                still_open.append(pr)
                continue
            mergeable_green += 1
            if not live or not head:
                still_open.append(pr)
                continue
            tri = compose_pr_triage(
                config_path=config_path,
                repo=repo_name,
                pr_number=pr_num,
                branch=head,
                live=True,
            )
            actions.append(
                {"step": "pr_triage", "pr": pr_num, "branch": head, **tri}
            )
            if not tri.get("ok"):
                still_open.append(pr)
                continue
            if tri.get("skipped"):
                tri_reason = str(tri.get("reason") or "")
                if tri.get("waiting") or tri_reason in {
                    "checks_pending",
                    "checks_none_require_checks",
                }:
                    if tri_reason == "checks_pending":
                        pending_checks += 1
                    elif tri_reason == "checks_none_require_checks":
                        no_checks_blocked += 1
                    mergeable_green = max(0, mergeable_green - 1)
                elif tri.get("repairable") or tri_reason == "checks_failed":
                    needs_repair += 1
                    if tri_reason == "checks_failed":
                        mergeable_green = max(0, mergeable_green - 1)
                    if repair_budget > 0 and executor_enabled:
                        repair = compose_pr_repair(
                            config_path=config_path,
                            repo=repo_name,
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
                    mergeable_green = max(0, mergeable_green - 1)
                    review_limbo += 1
                if tri.get("reason") == "merge_conflicts":
                    merge_conflicts += 1
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
                still_open.append(pr)
                continue
            progress += 1
            remaining_prs = max(0, remaining_prs - 1)
            mergeable_green = max(0, mergeable_green - 1)
            issue_n = issue_number_from_branch(head, branch_prefix=branch_prefix)
            if issue_n is not None:
                clear_issue(stuck, repo_name, issue_n)
                save_stuck(stuck_path, stuck)
        prs_by_repo[repo_name] = still_open

    if live:
        save_stuck(stuck_path, stuck)

    begin["repair_budget"] = repair_budget
    working.update(
        {
            "actions": actions,
            "progress": progress,
            "stuck": stuck,
            "prs_by_repo": prs_by_repo,
            "remaining_prs": remaining_prs,
            "pending_checks": pending_checks,
            "no_checks_blocked": no_checks_blocked,
            "merge_conflicts": merge_conflicts,
            "needs_repair": needs_repair,
            "mergeable_green": mergeable_green,
            "review_limbo": review_limbo,
        }
    )
    recount_prs(working)
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        remaining_prs=int(working.get("remaining_prs") or 0),
        actionable_prs=int(working.get("actionable_prs") or 0),
        needs_repair=needs_repair,
        mergeable_green=mergeable_green,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-closeout-prs")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_closeout_prs(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
