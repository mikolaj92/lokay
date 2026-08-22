"""Thin for-each: remaining open AI PRs via lokay-closeout-pr + recount."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.working import (
    load_begin_working,
    recount_prs,
    save_begin_working,
    stuck_path_of,
)
from lokay.closeout import COUNTERS
from lokay.proc._common import add_config_live
from lokay.proc.closeout_pr import run_closeout_pr
from lokay.stuck import save_stuck


def run_closeout_prs(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin, working = load_begin_working(pass_dir)
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or {})
    stuck_path = stuck_path_of(begin)
    repair_budget = int(begin.get("repair_budget") or 0)
    prs_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("prs_by_repo") or {}).items()
    }
    remaining_prs = int(working.get("remaining_prs") or 0)
    totals = {key: int(working.get(key) or 0) for key in COUNTERS}
    merged_this_pass = [str(n) for n in list(working.get("merged_this_pass") or []) if n]
    skipped_repos: list[str] = []

    for repo_name in list(begin.get("repos") or []):
        still_open: list[dict[str, Any]] = []
        for pr in list(prs_by_repo.get(repo_name) or []):
            out = run_closeout_pr(
                repo=repo_name,
                pr=pr,
                config_path=config_path,
                live=live,
                merge_enabled=bool(begin.get("merge_enabled")),
                require_checks=bool(begin.get("require_checks")),
                repair_budget=repair_budget,
                executor_enabled=bool(begin.get("executor_enabled")),
                branch_prefix=str(begin.get("branch_prefix") or "ai/fix/"),
                stuck=stuck,
                stuck_path=stuck_path,
                catalog=list(begin.get("repos") or []),
            )
            actions.extend(out.get("actions") or [])
            repair_budget = int(out.get("repair_budget") or 0)
            progress += int(out.get("progress") or 0)
            remaining_prs = max(0, remaining_prs - int(out.get("remaining_closed") or 0))
            for key in COUNTERS:
                totals[key] += int(out.get(key) or 0)
            if out.get("still_open"):
                still_open.append(pr)
            elif repo_name not in merged_this_pass:
                merged_this_pass.append(repo_name)
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
            "merged_this_pass": merged_this_pass,
            **totals,
        }
    )
    recount_prs(working)
    save_begin_working(pass_dir, begin, working)
    result = ok(
        pass_dir=pass_dir,
        remaining_prs=int(working.get("remaining_prs") or 0),
        actionable_prs=int(working.get("actionable_prs") or 0),
        needs_repair=totals["needs_repair"],
        mergeable_green=totals["mergeable_green"],
        merge_disabled=totals["merge_disabled"],
    )
    if skipped_repos:
        result.update(
            skipped=True,
            reason="repo_not_delivered_by_mini_mill",
            skipped_repos=skipped_repos,
        )
    return result


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
