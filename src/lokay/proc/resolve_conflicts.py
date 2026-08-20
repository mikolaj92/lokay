"""One job: close CONFLICTING/DIRTY AI PRs and re-ready linked issues."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.passkit.working import (
    load_begin_working,
    recount_prs,
    save_begin_working,
    stuck_path_of,
)
from lokay.proc import pr_close as p_pr_close
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live
from lokay.stuck import clear_issue, issue_number_from_branch, save_stuck
from lokay.mill_scope import SKIP_REASON, in_scope, mill_repo


MINI_MILL_REPO = mill_repo()


def run_resolve_conflicts(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or {})
    stuck_path = stuck_path_of(begin)
    branch_prefix = str(begin.get("branch_prefix") or "ai/fix/")
    prs_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("prs_by_repo") or {}).items()
    }
    ready_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("ready_by_repo") or {}).items()
    }
    remaining_prs = int(working.get("remaining_prs") or 0)
    remaining_ready = int(working.get("remaining_ready") or 0)
    merge_conflicts = int(working.get("merge_conflicts") or 0)
    closed = 0
    skipped_repos: list[str] = []

    for repo_name in list(begin.get("repos") or []):
        if not in_scope(repo_name, begin.get("repos") or [], mill=MINI_MILL_REPO):
            skipped_repos.append(repo_name)
            actions.append(
                {
                    "step": "skip_resolve_conflicts_outside_mini_scope",
                    "repo": repo_name,
                    "reason": SKIP_REASON,
                }
            )
            continue
        pr_list = list(prs_by_repo.get(repo_name) or [])
        still_open: list[dict[str, Any]] = []
        for pr in pr_list:
            if is_manual_pr(pr):
                still_open.append(pr)
                continue
            pr_num = int(pr["number"])
            head = str(pr.get("head_ref") or "")
            mergeable = str(pr.get("mergeable") or "").upper()
            if mergeable not in {"CONFLICTING", "DIRTY"}:
                still_open.append(pr)
                continue
            merge_conflicts += 1
            actions.append(
                {
                    "step": "pr_conflict",
                    "pr": pr_num,
                    "mergeable": mergeable,
                    "branch": head,
                }
            )
            if not live:
                still_open.append(pr)
                continue
            issue_n = issue_number_from_branch(head, branch_prefix=branch_prefix)
            comment = (
                f"Lokay closed PR #{pr_num}: mergeable={mergeable}. "
                "Will re-implement from current main."
            )
            closed_env = run_proc(
                p_pr_close.main,
                [
                    *cfg_flag,
                    *live_flag,
                    "--repo",
                    repo_name,
                    "--pr",
                    str(pr_num),
                    "--comment",
                    comment,
                ],
            )
            actions.append(
                {
                    "step": "pr_close_conflict",
                    "pr": pr_num,
                    "branch": head,
                    "issue": issue_n,
                    **closed_env,
                }
            )
            if not (
                closed_env.get("ok")
                and (closed_env.get("closed") or closed_env.get("planned"))
            ):
                still_open.append(pr)
                continue
            progress += 1
            closed += 1
            remaining_prs = max(0, remaining_prs - 1)
            merge_conflicts = max(0, merge_conflicts - 1)
            if issue_n is not None:
                clear_issue(stuck, repo_name, issue_n)
                save_stuck(stuck_path, stuck)
                ready_again = run_proc(
                    p_stage.main,
                    [
                        *cfg_flag,
                        *live_flag,
                        "--repo",
                        repo_name,
                        "--issue",
                        str(issue_n),
                        "--stage",
                        "ready",
                    ],
                )
                actions.append(
                    {
                        "step": "re_ready_after_conflict",
                        "repo": repo_name,
                        "issue": issue_n,
                        "pr": pr_num,
                        "stage": "ready",
                        **ready_again,
                    }
                )
                if ready_again.get("ok") and ready_again.get("applied"):
                    remaining_ready += 1
                    ready_by_repo.setdefault(repo_name, []).append(
                        {
                            "number": issue_n,
                            "repo": repo_name,
                            "title": str(pr.get("title") or f"issue {issue_n}"),
                        }
                    )
        prs_by_repo[repo_name] = still_open

    if live:
        save_stuck(stuck_path, stuck)

    working.update(
        {
            "actions": actions,
            "progress": progress,
            "stuck": stuck,
            "prs_by_repo": prs_by_repo,
            "ready_by_repo": ready_by_repo,
            "remaining_prs": remaining_prs,
            "remaining_ready": remaining_ready,
            "merge_conflicts": merge_conflicts,
        }
    )
    recount_prs(working)
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        closed=closed,
        merge_conflicts=merge_conflicts,
        skipped=bool(skipped_repos),
        reason=SKIP_REASON if skipped_repos else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-resolve-conflicts")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_resolve_conflicts(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
