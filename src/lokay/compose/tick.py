"""Composer: full multi-repo pass — inbox triage → ready → PR triage.

Always **surveys** all configured repos (read-only network) so a tick cannot
report green/planned while work remains. Mutations require --live + mode:live.

Stuck issues are isolated (failure ledger → ai:blocked). Idle only when the
survey finds no remaining actionable work.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from typing import Any, Callable

from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.compose.pr_repair import compose_pr_repair
from lokay.compose.pr_triage import compose_pr_triage
from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.proc import label_issue as p_label
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc import list_issues as p_list_issues
from lokay.proc import list_prs as p_list_prs
from lokay.proc import pr_checks as p_checks
from lokay.proc import pr_close as p_pr_close
from lokay.proc import select_issue as p_select
from lokay.proc import triage_issue as p_triage
from lokay.proc._common import add_config_live, load_cfg
from lokay.stuck import (
    clear_issue,
    excluded_numbers,
    issue_number_from_branch,
    issue_numbers_covered_by_prs,
    load_stuck,
    record_failure,
    save_stuck,
    stuck_path_for,
)


def _offline() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}


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


def _health_payload(
    *,
    cfg_mode: str,
    live: bool,
    executed: bool,
    progress: int,
    remaining: dict[str, Any],
    actions: list[dict[str, Any]],
    planned: list[dict[str, Any]],
    stuck_path: str | None,
    executor_enabled: bool,
) -> dict[str, Any]:
    inbox = int(remaining.get("inbox") or 0)
    ready = int(remaining.get("ready") or 0)  # implementable (no open AI PR yet)
    prs = int(remaining.get("open_ai_prs") or 0)
    mergeable_green = int(remaining.get("mergeable_green") or 0)
    needs_repair = int(remaining.get("needs_repair") or 0)
    repair_actionable = needs_repair if executor_enabled else 0
    # Ready issues need the agent slot when live.
    ready_actionable = ready if (not live or executor_enabled) else 0
    agent_blocked = bool(live and ready > 0 and not executor_enabled)

    if live:
        actionable_now = inbox + ready_actionable + mergeable_green + repair_actionable
    else:
        actionable_now = inbox + ready + prs

    idle = inbox == 0 and ready == 0 and prs == 0
    if idle:
        health = "idle"
    elif progress > 0:
        health = "progress"
    elif not live and actionable_now > 0:
        health = "work_remaining"
    elif agent_blocked and progress == 0 and inbox == 0 and mergeable_green == 0:
        # NOT WORKING: ready work exists but agent never runs.
        health = "stall"
    elif actionable_now > 0:
        health = "stall"
    else:
        health = "waiting"

    ok_flag = health not in {"stall", "work_remaining"}
    payload = ok(
        mode=cfg_mode,
        live=live,
        executed=executed,
        planned=planned,
        actions=actions,
        progress=progress,
        remaining=remaining,
        idle=idle,
        health=health,
        stuck_path=stuck_path,
        executor_enabled=executor_enabled,
    )
    if not ok_flag:
        payload["ok"] = False
        if health == "work_remaining":
            payload["error"] = "work_remaining: survey found actionable work (not idle)"
        elif agent_blocked and ready > 0:
            payload["error"] = (
                "stall: ready work remains but executor.enabled is false (agent never runs)"
            )
        else:
            payload["error"] = "stall: actionable work remains but no progress this pass"
    return payload


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

    pipeline = [
        "survey: list-inbox + list-issues + list-prs (all repos)",
        "lokay-list-inbox + lokay-triage-issue (or path issue_triage)",
        "lokay-list-issues + exclude stuck + select + issue_to_pr",
        "on failure: stuck ledger → ai:blocked",
        "list-prs + pr-checks; CONFLICTING → close+re-ready; failed → pr_repair; mergeable → pr_triage",
    ]
    planned.append(
        {
            "kind": "tick",
            "status": "mutating" if live else "survey",
            "repos": [r.name for r in cfg.active_repos()],
            "agent": cfg.agent,
            "pipeline": pipeline,
        }
    )

    if _offline():
        return ok(
            mode=cfg.mode,
            live=live,
            executed=False,
            planned=planned,
            actions=actions,
            idle=False,
            remaining={"note": "offline"},
            health="offline",
            progress=0,
        )

    remaining_inbox = 0
    remaining_ready = 0
    remaining_ready_with_pr = 0
    remaining_prs = 0
    needs_repair = 0
    mergeable_green = 0
    triage_budget = max(0, int(cfg.max_triage_per_tick)) if live else 0
    issue_budget = max(0, int(cfg.max_issues_per_tick)) if live else 0
    repair_budget = max(0, int(cfg.max_repairs_per_tick)) if live else 0
    max_fail = max(1, int(cfg.max_failures_before_block))

    stuck_path = stuck_path_for(cfg.state_path)
    stuck = load_stuck(stuck_path)

    # --- 0) PR heads first (filter ready issues already covered by open AI PRs) ---
    prs_by_repo: dict[str, list[dict[str, Any]]] = {}
    for repo in cfg.active_repos():
        prs = _run(p_list_prs.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_prs", "repo": repo.name, **prs})
        pr_list = list(prs.get("prs") or []) if prs.get("ok") else []
        prs_by_repo[repo.name] = pr_list
        remaining_prs += len(pr_list)

    # --- 1) Inbox: always survey; triage only when live ---
    for repo in cfg.active_repos():
        listed = _run(p_list_inbox.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_inbox", "repo": repo.name, **listed})
        if not listed.get("ok"):
            continue
        inbox = list(listed.get("issues") or [])
        remaining_inbox += len(inbox)
        if not live:
            continue
        for issue in inbox:
            if triage_budget <= 0:
                break
            num = int(issue["number"])
            # Prefer atom triage (Fala host may abort; opt-in LOKAY_USE_FALA=1).
            from lokay.compose._atoms import use_fala

            if use_fala():
                try:
                    tri = run_path(
                        path_id="issue_triage",
                        repo=repo.name,
                        issue=num,
                        config_path=config_path,
                        live=True,
                    )
                    actions.append(
                        {"step": "issue_triage", "repo": repo.name, "issue": num, **tri}
                    )
                    if tri.get("ok"):
                        progress += 1
                        remaining_inbox = max(0, remaining_inbox - 1)
                    triage_budget -= 1
                    continue
                except Exception:
                    pass
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

    # --- 2) Ready: survey; skip issues that already have open AI PRs; implement if live ---
    for repo in cfg.active_repos():
        listed = _run(p_list_issues.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_issues", "repo": repo.name, **listed})
        if not listed.get("ok"):
            continue
        issues = list(listed.get("issues") or [])
        covered = issue_numbers_covered_by_prs(
            prs_by_repo.get(repo.name) or [],
            branch_prefix=cfg.branch_prefix,
        )
        skip = excluded_numbers(stuck, repo.name) | covered
        if covered:
            actions.append(
                {
                    "step": "skip_ready_with_open_pr",
                    "repo": repo.name,
                    "issues": sorted(covered),
                }
            )
            covered_ready = [
                i for i in issues if int(i.get("number", -1)) in covered
            ]
            remaining_ready_with_pr += len(covered_ready)
            # Live: drop ai:ready so PR triage owns the work (no re-implement).
            if live and covered_ready:
                for issue in covered_ready:
                    num = int(issue["number"])
                    unlab = _run(
                        p_label.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            repo.name,
                            "--issue",
                            str(num),
                            "--label",
                            cfg.ready_label,
                            "--remove",
                        ],
                    )
                    actions.append(
                        {
                            "step": "unready_with_open_pr",
                            "repo": repo.name,
                            "issue": num,
                            **unlab,
                        }
                    )
                    if unlab.get("ok") and unlab.get("applied"):
                        progress += 1
                        remaining_ready_with_pr = max(0, remaining_ready_with_pr - 1)
        if excluded_numbers(stuck, repo.name):
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo.name,
                    "exclude": sorted(excluded_numbers(stuck, repo.name)),
                }
            )
        implementable = [i for i in issues if int(i.get("number", -1)) not in skip]
        remaining_ready += len(implementable)
        # Live implement only when agent slot can run — never fake progress.
        if not live or issue_budget <= 0:
            continue
        if implementable and not cfg.executor_enabled:
            actions.append(
                {
                    "step": "skip_ready_agent_disabled",
                    "repo": repo.name,
                    "count": len(implementable),
                    "note": "executor.enabled is false; refuse issue_to_pr",
                }
            )
            continue
        while implementable and issue_budget > 0:
            buf_in = json.dumps(
                {
                    "issues": implementable,
                    "exclude": sorted(skip),
                }
            )
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
                # Same-pass PR triage must see the new open AI PR (no false idle).
                pr_n = result.get("pr")
                br = str(result.get("branch") or "")
                if pr_n is not None and br:
                    remaining_prs += 1
                    prs_by_repo.setdefault(selected["repo"], []).append(
                        {
                            "number": int(pr_n),
                            "head_ref": br,
                            "mergeable": "UNKNOWN",
                            "title": str(
                                (selected.get("title") if isinstance(selected, dict) else "")
                                or ""
                            ),
                        }
                    )
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
                        progress += 1
                        remaining_ready = max(0, remaining_ready - 1)
            issue_budget -= 1
            implementable = [i for i in implementable if int(i.get("number", -1)) != num]

    if live:
        save_stuck(stuck_path, stuck)

    # --- 3) PR triage (reuse surveyed PR list): repair/merge when live ---
    pending_checks = 0
    no_checks_blocked = 0
    merge_conflicts = 0
    for repo in cfg.active_repos():
        pr_list = prs_by_repo.get(repo.name) or []
        for pr in pr_list:
            pr_num = int(pr["number"])
            head = str(pr.get("head_ref") or "")
            mergeable = str(pr.get("mergeable") or "").upper()
            if mergeable in {"CONFLICTING", "DIRTY"}:
                merge_conflicts += 1
                actions.append(
                    {
                        "step": "pr_conflict",
                        "pr": pr_num,
                        "mergeable": mergeable,
                        "branch": head,
                    }
                )
                # Dead PR: close + re-queue linked issue so mill can re-implement
                # from current main (stuck one conflict must not freeze ready work).
                if not live:
                    continue
                issue_n = issue_number_from_branch(
                    head, branch_prefix=cfg.branch_prefix
                )
                comment = (
                    f"Lokay closed PR #{pr_num}: mergeable={mergeable}. "
                    "Will re-implement from current main."
                )
                closed = _run(
                    p_pr_close.main,
                    [
                        *cfg_flag,
                        *live_flag,
                        "--repo",
                        repo.name,
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
                        **closed,
                    }
                )
                if not (closed.get("ok") and (closed.get("closed") or closed.get("planned"))):
                    continue
                progress += 1
                remaining_prs = max(0, remaining_prs - 1)
                merge_conflicts = max(0, merge_conflicts - 1)
                if issue_n is not None:
                    # Drop stuck ledger so a fresh issue_to_pr can run.
                    clear_issue(stuck, repo.name, issue_n)
                    save_stuck(stuck_path, stuck)
                    ready_again = _run(
                        p_label.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            repo.name,
                            "--issue",
                            str(issue_n),
                            "--label",
                            cfg.ready_label,
                        ],
                    )
                    actions.append(
                        {
                            "step": "re_ready_after_conflict",
                            "repo": repo.name,
                            "issue": issue_n,
                            "pr": pr_num,
                            **ready_again,
                        }
                    )
                    if ready_again.get("ok") and ready_again.get("applied"):
                        remaining_ready += 1
                continue
            chk = _run(
                p_checks.main,
                [*cfg_flag, "--repo", repo.name, "--pr", str(pr_num)],
            )
            actions.append({"step": "pr_checks", "pr": pr_num, **chk})
            if not chk.get("ok"):
                continue
            status = str(chk.get("status") or ("passed" if chk.get("green") else "failed"))
            # Failed CI → repair path (not "no checks").
            if status == "failed":
                needs_repair += 1
                if live and repair_budget > 0 and cfg.executor_enabled and head:
                    repair = compose_pr_repair(
                        config_path=config_path,
                        repo=repo.name,
                        pr_number=pr_num,
                        branch=head,
                        live=True,
                    )
                    actions.append(
                        {"step": "pr_repair", "pr": pr_num, "branch": head, **repair}
                    )
                    repair_budget -= 1
                    if repair.get("ok"):
                        progress += 1
                        needs_repair = max(0, needs_repair - 1)
                continue
            if status == "pending":
                pending_checks += 1
                continue
            if status == "none":
                # No CI on branch: merge only when require_checks is false.
                if cfg.require_checks:
                    no_checks_blocked += 1
                    continue
                # fall through as merge_ok
            elif status not in {"passed", "offline"} and not chk.get("merge_ok"):
                continue
            # merge_ok from atom, or passed / allowed none
            can_merge = bool(chk.get("merge_ok")) or status == "passed" or (
                status == "none" and not cfg.require_checks
            )
            if not can_merge:
                continue
            if not cfg.merge_enabled:
                # Count as mergeable under policy once merge is turned on.
                mergeable_green += 1
                continue
            mergeable_green += 1
            if not live or not head:
                continue
            # pr_triage: atom pipeline (or Fala if LOKAY_USE_FALA=1).
            tri = compose_pr_triage(
                config_path=config_path,
                repo=repo.name,
                pr_number=pr_num,
                branch=head,
                live=True,
            )
            actions.append(
                {"step": "pr_triage", "pr": pr_num, "branch": head, **tri}
            )
            if not tri.get("ok"):
                continue
            if tri.get("skipped"):
                # PR still open — keep remaining_prs; isolate conflicts.
                if tri.get("reason") == "merge_conflicts":
                    merge_conflicts += 1
                continue
            # Successful merge (+ optional close).
            progress += 1
            remaining_prs = max(0, remaining_prs - 1)
            mergeable_green = max(0, mergeable_green - 1)
            issue_n = issue_number_from_branch(head, branch_prefix=cfg.branch_prefix)
            if issue_n is not None:
                clear_issue(stuck, repo.name, issue_n)
                save_stuck(stuck_path, stuck)

    remaining = {
        "inbox": remaining_inbox,
        "ready": remaining_ready,
        "ready_with_open_pr": remaining_ready_with_pr,
        "open_ai_prs": remaining_prs,
        "mergeable_green": mergeable_green,
        "needs_repair": needs_repair,
        "pending_checks": pending_checks,
        "no_checks_blocked": no_checks_blocked,
        "merge_conflicts": merge_conflicts,
        "blocked_this_pass": blocked_this_pass,
    }
    return _health_payload(
        cfg_mode=cfg.mode,
        live=live,
        executed=live,
        progress=progress,
        remaining=remaining,
        actions=actions,
        planned=planned,
        stuck_path=str(stuck_path),
        executor_enabled=cfg.executor_enabled,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-tick")
    add_config_live(p)
    args = p.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
