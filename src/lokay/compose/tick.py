"""Composer: full multi-repo pass — inbox triage → ready → PR peek.

Stuck issues are isolated (failure ledger → ai:blocked) so one failure cannot
starve other ready work. Idle only when no remaining actionable work remains.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from typing import Any, Callable

from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.compose.pr_repair import compose_pr_repair
from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.proc import close_issue as p_close
from lokay.proc import label_issue as p_label
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc import list_issues as p_list_issues
from lokay.proc import list_prs as p_list_prs
from lokay.proc import pr_checks as p_checks
from lokay.proc import pr_merge as p_merge
from lokay.proc import select_issue as p_select
from lokay.proc import triage_issue as p_triage
from lokay.proc._common import add_config_live, load_cfg
from lokay.stuck import (
    clear_issue,
    excluded_numbers,
    issue_number_from_branch,
    load_stuck,
    record_failure,
    save_stuck,
    stuck_path_for,
)


def _run(main_fn: Callable[..., int], argv: list[str]) -> dict[str, Any]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main_fn(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty process output", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def compose_tick(*, config_path: str | None, live: bool) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    if live and cfg.mode != "live":
        return err("refusing --live while config mode is not live")

    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    planned: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    progress = 0
    blocked_this_pass = 0

    if not live:
        planned.append(
            {
                "kind": "tick",
                "status": "planned",
                "repos": [r.name for r in cfg.repos],
                "agent": cfg.agent,
                "pipeline": [
                    "lokay-list-inbox + lokay-triage-issue (or path issue_triage)",
                    "lokay-list-issues + exclude stuck + lokay-select-issue + lokay-issue-to-pr",
                    "on failure: stuck ledger; after N fails → lokay-label-issue ai:blocked",
                    "lokay-list-prs + lokay-pr-checks",
                    "red checks → Fala pr_repair (agent fix + push) when executor enabled",
                    "green + merge.enabled → merge + close linked issue",
                ],
            }
        )
        return ok(
            mode=cfg.mode,
            live=False,
            executed=False,
            planned=planned,
            actions=actions,
            idle=False,
            remaining={"note": "unknown_until_live_or_network"},
            health="planned",
        )

    remaining_inbox = 0
    remaining_ready = 0
    remaining_prs = 0
    needs_repair = 0
    triage_budget = max(0, int(cfg.max_triage_per_tick))
    issue_budget = max(0, int(cfg.max_issues_per_tick))
    repair_budget = max(0, int(cfg.max_repairs_per_tick))
    max_fail = max(1, int(cfg.max_failures_before_block))

    stuck_path = stuck_path_for(cfg.state_path)
    stuck = load_stuck(stuck_path)

    # --- 1) Inbox triage across all repos ---
    for repo in cfg.repos:
        listed = _run(p_list_inbox.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_inbox", "repo": repo.name, **listed})
        if not listed.get("ok"):
            continue
        inbox = list(listed.get("issues") or [])
        remaining_inbox += len(inbox)
        for issue in inbox:
            if triage_budget <= 0:
                break
            num = int(issue["number"])
            try:
                tri = run_path(
                    path_id="issue_triage",
                    repo=repo.name,
                    issue=num,
                    config_path=config_path,
                    live=True,
                )
                actions.append({"step": "issue_triage", "repo": repo.name, "issue": num, **tri})
                if tri.get("ok"):
                    progress += 1
                    remaining_inbox = max(0, remaining_inbox - 1)
            except Exception:
                tri = _run(
                    p_triage.main,
                    [*cfg_flag, *live_flag, "--repo", repo.name, "--issue", str(num)],
                )
                actions.append({"step": "triage_issue", "repo": repo.name, **tri})
                if tri.get("ok") and (
                    tri.get("applied") or tri.get("decision", {}).get("decision") != "skip"
                ):
                    progress += 1
                    remaining_inbox = max(0, remaining_inbox - 1)
            triage_budget -= 1

    # --- 2) Ready intake with stuck isolation ---
    for repo in cfg.repos:
        if issue_budget <= 0:
            break
        listed = _run(p_list_issues.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_issues", "repo": repo.name, **listed})
        if not listed.get("ok"):
            continue
        issues = list(listed.get("issues") or [])
        skip = excluded_numbers(stuck, repo.name)
        if skip:
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo.name,
                    "exclude": sorted(skip),
                }
            )
        remaining_ready += len(issues)
        # Prefer non-stuck; never re-select ledger-blocked numbers this pass.
        while issues and issue_budget > 0:
            eligible = [i for i in issues if int(i.get("number", -1)) not in skip]
            if not eligible:
                break
            buf_in = json.dumps({"issues": eligible, "exclude": sorted(skip)})
            buf_out = io.StringIO()
            old_stdin = sys.stdin
            try:
                sys.stdin = io.StringIO(buf_in)
                with contextlib.redirect_stdout(buf_out):
                    code = p_select.main([])
            finally:
                sys.stdin = old_stdin
            sel = json.loads(buf_out.getvalue().strip().splitlines()[-1])
            sel["_exit"] = code
            actions.append({"step": "select_issue", "repo": repo.name, **sel})
            selected = sel.get("selected")
            if not selected:
                break
            num = int(selected["number"])
            result = compose_issue_to_pr(
                config_path=config_path,
                repo=selected["repo"],
                issue_number=num,
                live=True,
            )
            actions.append({"step": "issue_to_pr", **result})
            if result.get("ok"):
                progress += 1
                remaining_ready = max(0, remaining_ready - 1)
                clear_issue(stuck, selected["repo"], num)
            else:
                row = record_failure(
                    stuck,
                    repo=selected["repo"],
                    number=num,
                    error=str(result.get("error") or result.get("fala") or "issue_to_pr failed"),
                    max_failures=max_fail,
                )
                actions.append(
                    {
                        "step": "record_stuck",
                        "repo": selected["repo"],
                        "issue": num,
                        "failures": row.get("failures"),
                        "blocked": bool(row.get("blocked")),
                    }
                )
                if row.get("blocked"):
                    skip.add(num)
                    blocked_this_pass += 1
                    lab = _run(
                        p_label.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            selected["repo"],
                            "--issue",
                            str(num),
                            "--label",
                            cfg.blocked_label,
                        ],
                    )
                    actions.append({"step": "label_blocked", **lab})
                    if lab.get("ok") and lab.get("applied"):
                        progress += 1  # isolation is progress (unblocks mill)
                        remaining_ready = max(0, remaining_ready - 1)
            issue_budget -= 1
            issues = [i for i in issues if int(i.get("number", -1)) != num]

    save_stuck(stuck_path, stuck)

    # --- 3) PR triage: repair red checks, merge green when policy allows ---
    mergeable_green = 0
    for repo in cfg.repos:
        prs = _run(p_list_prs.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_prs", "repo": repo.name, **prs})
        if not prs.get("ok"):
            continue
        pr_list = list(prs.get("prs") or [])
        remaining_prs += len(pr_list)
        for pr in pr_list:
            pr_num = int(pr["number"])
            head = str(pr.get("head_ref") or "")
            chk = _run(
                p_checks.main,
                [*cfg_flag, "--repo", repo.name, "--pr", str(pr_num)],
            )
            actions.append({"step": "pr_checks", "pr": pr_num, **chk})
            if not chk.get("ok"):
                continue
            if not chk.get("green"):
                needs_repair += 1
                # Repair when executor is on and budget remains; one red PR must not
                # block later green merges in the same pass.
                if repair_budget > 0 and cfg.executor_enabled and head:
                    repair = compose_pr_repair(
                        config_path=config_path,
                        repo=repo.name,
                        pr_number=pr_num,
                        branch=head,
                        live=True,
                    )
                    actions.append(
                        {
                            "step": "pr_repair",
                            "pr": pr_num,
                            "branch": head,
                            **repair,
                        }
                    )
                    repair_budget -= 1
                    if repair.get("ok"):
                        progress += 1
                        needs_repair = max(0, needs_repair - 1)
                continue
            if not cfg.merge_enabled:
                continue
            mergeable_green += 1
            merged = _run(
                p_merge.main,
                [*cfg_flag, *live_flag, "--repo", repo.name, "--pr", str(pr_num)],
            )
            actions.append({"step": "pr_merge", "pr": pr_num, **merged})
            if not (merged.get("ok") and merged.get("merged")):
                continue
            progress += 1
            remaining_prs = max(0, remaining_prs - 1)
            mergeable_green = max(0, mergeable_green - 1)
            issue_n = issue_number_from_branch(
                head,
                branch_prefix=cfg.branch_prefix,
            )
            if issue_n is not None:
                closed = _run(
                    p_close.main,
                    [
                        *cfg_flag,
                        *live_flag,
                        "--repo",
                        repo.name,
                        "--issue",
                        str(issue_n),
                        "--comment",
                        f"Closed by Lokay after merging PR #{pr_num}.",
                    ],
                )
                actions.append(
                    {
                        "step": "close_issue",
                        "issue": issue_n,
                        "pr": pr_num,
                        **closed,
                    }
                )
                if closed.get("ok") and closed.get("closed"):
                    progress += 1
                    clear_issue(stuck, repo.name, issue_n)
                    save_stuck(stuck_path, stuck)

    remaining = {
        "inbox": remaining_inbox,
        "ready": remaining_ready,
        "open_ai_prs": remaining_prs,
        "mergeable_green": mergeable_green,
        "needs_repair": needs_repair,
        "blocked_this_pass": blocked_this_pass,
    }
    # Red PRs are only "actionable now" when the agent slot can run repairs.
    repair_actionable = needs_repair if cfg.executor_enabled else 0
    actionable_now = remaining_inbox + remaining_ready + mergeable_green + repair_actionable
    idle = remaining_inbox == 0 and remaining_ready == 0 and remaining_prs == 0
    if idle:
        health = "idle"
    elif progress > 0:
        health = "progress"
    elif actionable_now > 0:
        health = "stall"
    else:
        health = "waiting"
    ok_flag = health != "stall"
    payload = ok(
        mode=cfg.mode,
        live=True,
        executed=True,
        planned=planned,
        actions=actions,
        progress=progress,
        remaining=remaining,
        idle=idle,
        health=health,
        stuck_path=str(stuck_path),
    )
    if not ok_flag:
        payload["ok"] = False
        payload["error"] = "stall: actionable work remains but no progress this pass"
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-tick")
    add_config_live(p)
    args = p.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
