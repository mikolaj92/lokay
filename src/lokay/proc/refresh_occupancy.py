"""One job: after closeout, refresh which repos are occupied for implement.

Start-of-pass ``survey_prs`` is stale once closeout merges or a live
``issue_to_pr`` is still coding. Re-list open AI PRs, union just-merged
repos and live receipts, write occupancy so ``select_implement`` cannot
start a sibling i2pr on a dirty / settling repo.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.passkit.working import load_begin_working, recount_prs, save_begin_working
from lokay.proc import list_prs as p_list_prs
from lokay.proc._common import add_config_live
from lokay.proc.detach_issue_to_pr import live_issue_to_pr_receipts


def _merged_this_pass(working: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for repo_name in list(working.get("merged_this_pass") or []):
        name = str(repo_name or "")
        if name and name not in seen:
            seen.append(name)
    return seen


def run_refresh_occupancy(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
) -> dict[str, Any]:
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    previous = dict(working.get("prs_by_repo") or {})
    prs_by_repo: dict[str, list[dict[str, Any]]] = {}
    pr_survey_failed: list[str] = []
    remaining_prs = 0
    actionable_prs = 0
    manual_prs = 0
    pr_errors = 0

    for repo_name in list(begin.get("repos") or []):
        prs = run_proc(p_list_prs.main, [*cfg_flag, *live_flag, "--repo", repo_name])
        actions.append({"step": "refresh_prs", "repo": repo_name, **prs})
        if not prs.get("ok"):
            pr_errors += 1
            pr_survey_failed.append(repo_name)
            prs_by_repo[repo_name] = []
            continue
        prev = {
            int(row["number"]): row
            for row in list(previous.get(repo_name) or [])
            if row.get("number") is not None
        }
        pr_list: list[dict[str, Any]] = []
        for row in list(prs.get("prs") or []):
            parked = prev.get(int(row["number"])) if row.get("number") is not None else None
            if parked is not None and is_manual_pr(parked) and not is_manual_pr(row):
                labels = list(row.get("labels") or [])
                row = {**row, "labels": [*labels, "ai:needs-review"]}
            pr_list.append(row)
        prs_by_repo[repo_name] = pr_list
        remaining_prs += len(pr_list)
        actionable_prs += sum(not is_manual_pr(pr) for pr in pr_list)
        manual_prs += sum(is_manual_pr(pr) for pr in pr_list)

    merged = _merged_this_pass(working)
    live_rows = live_issue_to_pr_receipts()
    live_repos: list[str] = []
    for row in live_rows:
        repo_name = str(row.get("repo") or "")
        if repo_name and repo_name not in live_repos:
            live_repos.append(repo_name)

    occupied = list(dict.fromkeys([*merged, *live_repos]))
    inbox_failed = len(working.get("inbox_survey_failed") or [])
    ready_failed = len(working.get("ready_survey_failed") or [])

    working.update(
        {
            "actions": actions,
            "prs_by_repo": prs_by_repo,
            "pr_survey_failed": sorted(pr_survey_failed),
            "remaining_prs": remaining_prs,
            "actionable_prs": actionable_prs,
            "manual_prs": manual_prs,
            "survey_errors": inbox_failed + ready_failed + pr_errors,
            "merged_this_pass": merged,
            "live_issue_to_pr_repos": live_repos,
            "occupied_repos": occupied,
        }
    )
    recount_prs(working)
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        occupied_repos=occupied,
        merged_this_pass=merged,
        live_issue_to_pr_repos=live_repos,
        remaining_prs=int(working.get("remaining_prs") or 0),
        actionable_prs=int(working.get("actionable_prs") or 0),
        survey_errors=int(working.get("survey_errors") or 0),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-refresh-occupancy")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_refresh_occupancy(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
