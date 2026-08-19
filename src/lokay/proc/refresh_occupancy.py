"""One job: after closeout, mark occupied repos for implement.

Start-of-pass ``survey_prs`` is stale once closeout merges or a live
``issue_to_pr`` is still coding. Union just-merged + live receipts first.
Re-list open AI PRs only on leftover-ready repos that are not occupied.
A 29-repo refresh after a full survey is what 429s the secondary budget.
"""

from __future__ import annotations

import argparse
import os
import signal
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.passkit.working import load_begin_working, recount_prs, save_begin_working
from lokay.proc import get_issue as p_get_issue
from lokay.proc import list_prs as p_list_prs
from lokay.proc._common import add_config_live
from lokay.proc.detach_issue_to_pr import (
    clear_dead_issue_to_pr_receipts,
    clear_issue_to_pr_receipt,
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)


def _merged_this_pass(working: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for repo_name in list(working.get("merged_this_pass") or []):
        name = str(repo_name or "")
        if name and name not in seen:
            seen.append(name)
    return seen


def _terminate_issue_to_pr(receipt: dict[str, Any]) -> bool:
    try:
        pid = int(receipt["pid"])
        if pid <= 0:
            return False
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except (KeyError, TypeError, ValueError, OSError):
        return False
    return True


def _live_repos(
    *, cfg_flag: list[str], live_flag: list[str], actions: list[dict[str, Any]]
) -> tuple[list[str], list[dict[str, Any]]]:
    live_repos: list[str] = []
    cleared: list[dict[str, Any]] = []
    for receipt in live_issue_to_pr_receipts():
        repo_name = str(receipt.get("repo") or "")
        try:
            issue_number = int(receipt["issue"])
        except (KeyError, TypeError, ValueError):
            continue
        viewed = run_proc(
            p_get_issue.main,
            [*cfg_flag, *live_flag, "--repo", repo_name, "--issue", str(issue_number)],
        )
        actions.append(
            {
                "step": "get_live_issue_to_pr_issue",
                **viewed,
                "repo": repo_name,
                "issue": issue_number,
            }
        )
        # A failed lookup is uncertainty, so retain occupancy. Only an
        # authoritative non-OPEN state makes a live worker's lane idle.
        state = str((viewed.get("issue") or {}).get("state") or "").upper()
        if viewed.get("ok") and state and state != "OPEN":
            if _terminate_issue_to_pr(receipt) and clear_issue_to_pr_receipt(receipt):
                cleared.append(receipt)
                continue
            # The receipt changed concurrently or could not be removed; keep
            # the lane occupied rather than racing a replacement worker.
        if repo_name and repo_name not in live_repos:
            live_repos.append(repo_name)
    return live_repos, cleared


def _keep_parked_labels(
    previous: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prev = {
        int(row["number"]): row
        for row in previous
        if row.get("number") is not None
    }
    kept: list[dict[str, Any]] = []
    for row in rows:
        parked = prev.get(int(row["number"])) if row.get("number") is not None else None
        if parked is not None and is_manual_pr(parked) and not is_manual_pr(row):
            labels = list(row.get("labels") or [])
            row = {**row, "labels": [*labels, "ai:needs-review"]}
        kept.append(row)
    return kept


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
    ready_by_repo = dict(working.get("ready_by_repo") or {})
    merged = _merged_this_pass(working)
    cleared_receipts = clear_dead_issue_to_pr_receipts(merged)
    for receipt in cleared_receipts:
        actions.append(
            {
                "step": "clear_issue_to_pr_receipt",
                "repo": receipt.get("repo"),
                "issue": receipt.get("issue"),
            }
        )
    receipt_state_unknown = has_unreadable_issue_to_pr_receipts()
    live_repos, closed_receipts = _live_repos(
        cfg_flag=cfg_flag, live_flag=live_flag, actions=actions
    )
    cleared_receipts.extend(closed_receipts)
    for receipt in closed_receipts:
        actions.append(
            {
                "step": "clear_closed_issue_to_pr_receipt",
                "repo": receipt.get("repo"),
                "issue": receipt.get("issue"),
            }
        )
    # Dead/stale/unreadable receipts are idle. Only a live coder or a merge
    # this pass occupies a repo. Occupying the whole catalog blocked dispatch.
    occupied = list(dict.fromkeys([*merged, *live_repos]))
    occupied_set = set(occupied)
    prs_by_repo: dict[str, list[dict[str, Any]]] = {}
    pr_survey_failed = set(working.get("pr_survey_failed") or [])

    for repo_name in list(begin.get("repos") or []):
        prev_list = list(previous.get(repo_name) or [])
        ready = list(ready_by_repo.get(repo_name) or [])
        if repo_name in occupied_set:
            actions.append(
                {
                    "step": "refresh_prs_skipped",
                    "repo": repo_name,
                    "reason": (
                        "receipt_state_unknown"
                        if receipt_state_unknown and repo_name not in merged and repo_name not in live_repos
                        else "occupied"
                    ),
                }
            )
            prs_by_repo[repo_name] = prev_list
            continue
        if not ready:
            actions.append(
                {
                    "step": "refresh_prs_skipped",
                    "repo": repo_name,
                    "reason": "no_ready",
                }
            )
            prs_by_repo[repo_name] = prev_list
            continue
        prs = run_proc(p_list_prs.main, [*cfg_flag, *live_flag, "--repo", repo_name])
        actions.append({"step": "refresh_prs", "repo": repo_name, **prs})
        if not prs.get("ok"):
            pr_survey_failed.add(repo_name)
            # Keep closeout / survey snapshot. Emptying it would look like
            # a clear lane and waste the next pass's rate budget.
            prs_by_repo[repo_name] = prev_list
            continue
        pr_survey_failed.discard(repo_name)
        prs_by_repo[repo_name] = _keep_parked_labels(
            prev_list, list(prs.get("prs") or [])
        )

    inbox_failed = len(working.get("inbox_survey_failed") or [])
    ready_failed = len(working.get("ready_survey_failed") or [])
    # Count every failed PR survey still on the board, not just this
    # atom's new 429s. A skipped occupied/no_ready repo keeps its flag.

    working.update(
        {
            "actions": actions,
            "prs_by_repo": prs_by_repo,
            "pr_survey_failed": sorted(pr_survey_failed),
            "survey_errors": inbox_failed + ready_failed + len(pr_survey_failed),
            "merged_this_pass": merged,
            "live_issue_to_pr_repos": live_repos,
            "occupied_repos": occupied,
            "cleared_issue_to_pr_receipts": [
                {
                    "repo": receipt.get("repo"),
                    "issue": receipt.get("issue"),
                }
                for receipt in cleared_receipts
            ],
        }
    )
    recount_prs(working)
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        occupied_repos=occupied,
        merged_this_pass=merged,
        live_issue_to_pr_repos=live_repos,
        cleared_issue_to_pr_receipts=working["cleared_issue_to_pr_receipts"],
        remaining_prs=int(working.get("remaining_prs") or 0),
        actionable_prs=int(working.get("actionable_prs") or 0),
        survey_errors=int(working.get("survey_errors") or 0),
        receipt_state_unknown=receipt_state_unknown,
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
