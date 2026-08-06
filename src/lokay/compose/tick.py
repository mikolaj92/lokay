"""Composer: full multi-repo pass — inbox triage → ready → PR peek.

Idle only when no remaining actionable work was observed after the pass.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from typing import Any, Callable

from lokay.compose.issue_to_pr import compose_issue_to_pr
from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc import list_issues as p_list_issues
from lokay.proc import list_prs as p_list_prs
from lokay.proc import pr_checks as p_checks
from lokay.proc import pr_merge as p_merge
from lokay.proc import select_issue as p_select
from lokay.proc import triage_issue as p_triage
from lokay.proc._common import add_config_live, load_cfg


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
    progress = 0  # steps that moved work forward

    if not live:
        planned.append(
            {
                "kind": "tick",
                "status": "planned",
                "repos": [r.name for r in cfg.repos],
                "agent": cfg.agent,
                "pipeline": [
                    "lokay-list-inbox + lokay-triage-issue (or path issue_triage)",
                    "lokay-list-issues + lokay-select-issue + lokay-issue-to-pr",
                    "lokay-list-prs + lokay-pr-checks (+ lokay-pr-merge if enabled)",
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
    triage_budget = max(0, int(cfg.max_triage_per_tick))
    issue_budget = max(0, int(cfg.max_issues_per_tick))

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
            # Prefer Fala issue_triage when available; fall back to atom.
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
                if tri.get("ok") and (tri.get("applied") or tri.get("decision", {}).get("decision") != "skip"):
                    progress += 1
                    remaining_inbox = max(0, remaining_inbox - 1)
            triage_budget -= 1

    # --- 2) Ready intake: walk repos until issue budget exhausted ---
    for repo in cfg.repos:
        if issue_budget <= 0:
            break
        listed = _run(p_list_issues.main, [*cfg_flag, "--repo", repo.name])
        actions.append({"step": "list_issues", "repo": repo.name, **listed})
        if not listed.get("ok"):
            continue
        issues = list(listed.get("issues") or [])
        remaining_ready += len(issues)
        while issues and issue_budget > 0:
            buf_in = json.dumps({"issues": issues})
            buf_out = io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stdin(io.StringIO(buf_in)):
                code = p_select.main([])
            sel = json.loads(buf_out.getvalue().strip().splitlines()[-1])
            sel["_exit"] = code
            actions.append({"step": "select_issue", "repo": repo.name, **sel})
            selected = sel.get("selected")
            if not selected:
                break
            result = compose_issue_to_pr(
                config_path=config_path,
                repo=selected["repo"],
                issue_number=int(selected["number"]),
                live=True,
            )
            actions.append({"step": "issue_to_pr", **result})
            if result.get("ok"):
                progress += 1
                remaining_ready = max(0, remaining_ready - 1)
            issue_budget -= 1
            # Drop selected so we can mill next ready in same repo
            issues = [i for i in issues if int(i.get("number", -1)) != int(selected["number"])]

    # --- 3) PR triage peek (+ merge when policy allows) ---
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
            chk = _run(
                p_checks.main,
                [*cfg_flag, "--repo", repo.name, "--pr", str(pr_num)],
            )
            actions.append({"step": "pr_checks", "pr": pr_num, **chk})
            if not chk.get("ok"):
                continue
            if chk.get("green"):
                if cfg.merge_enabled:
                    mergeable_green += 1
                    merged = _run(
                        p_merge.main,
                        [*cfg_flag, *live_flag, "--repo", repo.name, "--pr", str(pr_num)],
                    )
                    actions.append({"step": "pr_merge", "pr": pr_num, **merged})
                    if merged.get("ok") and merged.get("merged"):
                        progress += 1
                        remaining_prs = max(0, remaining_prs - 1)
                        mergeable_green = max(0, mergeable_green - 1)
                # else: green but merge disabled — waiting on human policy

    remaining = {
        "inbox": remaining_inbox,
        "ready": remaining_ready,
        "open_ai_prs": remaining_prs,
        "mergeable_green": mergeable_green,
    }
    # Actionable now: inbox to triage, ready to implement, or green PRs we can merge.
    actionable_now = remaining_inbox + remaining_ready + mergeable_green
    idle = remaining_inbox == 0 and remaining_ready == 0 and remaining_prs == 0
    if idle:
        health = "idle"
    elif progress > 0:
        health = "progress"
    elif actionable_now > 0:
        # Inbox/ready/mergeable work existed but nothing advanced — stall.
        health = "stall"
    else:
        # Open PRs waiting on CI or merge policy — not idle, not stall.
        health = "waiting"

    # Fail-closed: green noop while actionable work remains is NOT WORKING.
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
