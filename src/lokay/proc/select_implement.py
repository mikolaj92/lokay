"""One job: choose clean repos eligible for issue_to_pr after PR close-out."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr
from lokay.proc._common import add_config_live
from lokay.stuck import excluded_numbers, load_stuck


MINI_MILL_REPO = "mikolaj92/lokay"


def run_select_implement(*, pass_dir: str) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    live = bool(begin.get("live"))
    issue_budget = int(begin.get("issue_budget") or 0)
    executor_enabled = bool(begin.get("executor_enabled"))
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    prs_by_repo = dict(working.get("prs_by_repo") or {})
    ready_by_repo = dict(working.get("ready_by_repo") or {})
    pr_survey_failed = set(working.get("pr_survey_failed") or [])
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    stuck_path = str(begin.get("stuck_path") or "")
    if stuck_path and Path(stuck_path).is_file():
        stuck = load_stuck(Path(stuck_path))
    occupied = {
        str(name)
        for name in list(working.get("occupied_repos") or [])
        + list(working.get("merged_this_pass") or [])
        + list(working.get("live_issue_to_pr_repos") or [])
        if str(name or "")
    }
    clean_repos: list[str] = []
    repos = list(begin.get("repos") or [])
    lokay_mill = MINI_MILL_REPO in repos

    if not live or issue_budget <= 0:
        payload = {"clean_repos": [], "issue_budget": issue_budget, "reason": "no_live_budget"}
        pass_io.write_json(pass_io.implement_path(pass_dir), payload)
        working["actions"] = actions
        pass_io.write_json(pass_io.working_path(pass_dir), working)
        return ok(pass_dir=pass_dir, selected=0)

    for repo_name in repos:
        if lokay_mill and repo_name != MINI_MILL_REPO:
            actions.append(
                {
                    "step": "skip_issue_to_pr_outside_mini_scope",
                    "repo": repo_name,
                    "reason": f"mini mill only implements {MINI_MILL_REPO}",
                }
            )
            continue
        if repo_name in pr_survey_failed:
            actions.append(
                {
                    "step": "skip_issue_to_pr_survey_failed",
                    "repo": repo_name,
                    "reason": "PR survey failed closed for this repo; refuse issue_to_pr",
                }
            )
            continue
        open_prs = prs_by_repo.get(repo_name) or []
        actionable_prs = [pr for pr in open_prs if not is_manual_pr(pr)]
        if actionable_prs:
            actions.append(
                {
                    "step": "skip_ready_open_ai_pr",
                    "repo": repo_name,
                    "open_ai_prs": len(actionable_prs),
                    "note": "per-repo PR-first: finish actionable AI PR before new issue_to_pr",
                }
            )
            continue
        if repo_name in occupied:
            actions.append(
                {
                    "step": "skip_ready_repo_occupied",
                    "repo": repo_name,
                    "note": (
                        "repo just merged or still has a live issue_to_pr; "
                        "do not start a sibling from stale origin/main"
                    ),
                }
            )
            continue
        candidates = list(ready_by_repo.get(repo_name) or [])
        excluded = excluded_numbers(stuck, repo_name)
        blocked_candidates = [
            issue
            for issue in candidates
            if int(issue.get("number", -1)) in excluded
        ]
        implementable = [
            issue
            for issue in candidates
            if int(issue.get("number", -1)) not in excluded
        ]
        if blocked_candidates:
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo_name,
                    "exclude": sorted(
                        int(issue.get("number", -1)) for issue in blocked_candidates
                    ),
                    "reason": "issue is blocked in the stuck ledger; refuse issue_to_pr",
                }
            )
            ready_by_repo[repo_name] = implementable
            issue_budget_ready = len(blocked_candidates)
            working["remaining_ready"] = max(
                0, int(working.get("remaining_ready") or 0) - issue_budget_ready
            )
        if not implementable:
            continue
        if not executor_enabled:
            actions.append(
                {
                    "step": "skip_ready_agent_disabled",
                    "repo": repo_name,
                    "count": len(implementable),
                    "note": "executor.enabled is false; refuse issue_to_pr",
                }
            )
            continue
        clean_repos.append(repo_name)

    payload = {"clean_repos": clean_repos, "issue_budget": issue_budget}
    pass_io.write_json(pass_io.implement_path(pass_dir), payload)
    working["ready_by_repo"] = ready_by_repo
    working["actions"] = actions
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return ok(pass_dir=pass_dir, selected=len(clean_repos), issue_budget=issue_budget)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-select-implement")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_select_implement(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
