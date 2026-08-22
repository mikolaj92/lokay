"""One job: contradiction gate over ready candidates before issue_to_pr.

Covering-PR matches stay deterministic. Semantic remainder is one structured
agent call. Queue hygiene — not a parallel scheduler.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.models import Issue
from lokay.passkit import io as pass_io
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc import label_issue as p_label
from lokay.proc._common import add_config_live, load_cfg, runner, semantic_agent_allowed
from lokay.queue_conflict import READY, SKIP
from lokay.queue_conflict_agent import evaluate_queue_conflict_with_agent
from lokay.mill_scope import in_scope, mill_repo


MINI_MILL_REPO = mill_repo()


def evaluate_stdin(payload: dict[str, Any]) -> dict[str, Any]:
    """Single-candidate mode for tests / select enrichment."""
    raw = payload.get("issue") or payload.get("selected")
    if not isinstance(raw, dict):
        return err("stdin must include issue{} object")
    issue = Issue.from_dict(raw)
    verdict = evaluate_queue_conflict_with_agent(
        issue,
        runner=None,
        config=None,
        execute=False,
        open_prs=list(payload.get("open_prs") or []),
        peer_issues=list(payload.get("peer_issues") or []),
        branch_prefix=str(payload.get("branch_prefix") or "ai/fix/"),
        ready_label=str(payload.get("ready_label") or "ai:ready"),
        tracker_label=str(payload.get("tracker_label") or "ai:tracker"),
    )
    return ok(
        outcome=verdict.outcome,
        reason=verdict.reason,
        detail=verdict.detail,
        comment=verdict.comment,
        add_labels=verdict.add_labels,
        remove_labels=verdict.remove_labels,
        selected=issue.to_dict() if verdict.outcome == READY else None,
        verdict=verdict.to_dict(),
    )


def _demote_live(
    *,
    repo: str,
    issue_number: int,
    remove_labels: list[str],
    add_labels: list[str],
    cfg_flag: list[str],
    live_flag: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {"applied": False}
    for lab in remove_labels:
        env = run_proc(
            p_label.main,
            [
                *cfg_flag,
                *live_flag,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--label",
                lab,
                "--remove",
            ],
        )
        out[f"remove_{lab}"] = env
        if env.get("ok") and env.get("applied"):
            out["applied"] = True
    for lab in add_labels:
        env = run_proc(
            p_label.main,
            [
                *cfg_flag,
                *live_flag,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--label",
                lab,
            ],
        )
        out[f"add_{lab}"] = env
        if env.get("ok") and env.get("applied"):
            out["applied"] = True
    return out


def run_queue_conflict(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
) -> dict[str, Any]:
    """Pass-dir mode: filter ready_by_repo; demote CLOSE with receipt when live."""
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    cfg = load_cfg(argparse.Namespace(config=config_path)) if config_path or live else None
    execute = bool(cfg and semantic_agent_allowed(cfg, live_flag=live))
    r = runner(cfg) if execute and cfg is not None else None
    branch_prefix = str(begin.get("branch_prefix") or "ai/fix/")
    ready_label = str(begin.get("ready_label") or "ai:ready")
    tracker_label = "ai:tracker"
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    ready_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("ready_by_repo") or {}).items()
    }
    prs_by_repo = dict(working.get("prs_by_repo") or {})
    inbox_issues_by_repo = dict(working.get("inbox_issues_by_repo") or {})
    remaining_ready = int(working.get("remaining_ready") or 0)
    skipped = 0
    demoted = 0
    kept = 0

    implement_preview: dict[str, Any] = {}
    impl_path = pass_io.implement_path(pass_dir)
    if impl_path.is_file():
        implement_preview = pass_io.read_json(impl_path)
    clean_only = list(implement_preview.get("clean_repos") or [])
    scan_repos = clean_only or list(begin.get("repos") or [])
    # Dispatch starts at most one issue per repo. Gate that candidate (and a
    # few replacements if it is SKIP/CLOSE), not the whole ready catalog.
    per_repo_cap = 1
    hard_cap = 8

    for repo_name in scan_repos:
        ready = list(ready_by_repo.get(repo_name) or [])
        if not ready:
            ready_by_repo[repo_name] = []
            continue
        peers = list(ready) + list(inbox_issues_by_repo.get(repo_name) or [])
        open_prs = list(prs_by_repo.get(repo_name) or [])
        kept_ready: list[dict[str, Any]] = []
        examined = 0
        for issue in ready:
            if (kept_ready and examined >= per_repo_cap) or examined >= hard_cap:
                kept_ready.extend(ready[ready.index(issue) :])
                break
            examined += 1
            num = int(issue.get("number") or 0)
            verdict = evaluate_queue_conflict_with_agent(
                issue,
                runner=r,
                config=cfg,
                execute=execute,
                open_prs=open_prs,
                peer_issues=peers,
                branch_prefix=branch_prefix,
                ready_label=ready_label,
                tracker_label=tracker_label,
            )
            row: dict[str, Any] = {
                "step": "queue_conflict",
                "repo": repo_name,
                "issue": num,
                "outcome": verdict.outcome,
                "reason": verdict.reason,
                "detail": verdict.detail,
                "semantic": verdict.semantic,
            }
            if verdict.outcome == READY:
                kept_ready.append(issue)
                kept += 1
                actions.append(row)
                continue
            if verdict.outcome == SKIP:
                skipped += 1
                actions.append(row)
                remaining_ready = max(0, remaining_ready - 1)
                continue
            # CLOSE / demote — drop from this pass; mutate labels when live.
            demoted += 1
            remaining_ready = max(0, remaining_ready - 1)
            if live:
                apply = _demote_live(
                    repo=repo_name,
                    issue_number=num,
                    remove_labels=list(verdict.remove_labels),
                    add_labels=list(verdict.add_labels),
                    cfg_flag=cfg_flag,
                    live_flag=live_flag,
                )
                row.update(apply)
                if apply.get("applied"):
                    progress += 1
            else:
                row["planned"] = True
            if verdict.comment:
                row["comment"] = verdict.comment
            actions.append(row)
        ready_by_repo[repo_name] = kept_ready

    implement: dict[str, Any] = implement_preview
    if impl_path.is_file():
        clean = [
            r
            for r in list(implement.get("clean_repos") or [])
            if in_scope(r, begin.get("repos") or [], mill=MINI_MILL_REPO) and ready_by_repo.get(r)
        ]
        implement["clean_repos"] = clean
        pass_io.write_json(impl_path, implement)

    working.update(
        {
            "actions": actions,
            "progress": progress,
            "ready_by_repo": ready_by_repo,
            "remaining_ready": remaining_ready,
        }
    )
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        kept=kept,
        skipped=skipped,
        demoted=demoted,
        clean_repos=list(implement.get("clean_repos") or []),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-queue-conflict")
    add_config_live(parser)
    parser.add_argument(
        "--pass-dir",
        default="",
        help="factory pass workspace (filters ready_by_repo)",
    )
    args = parser.parse_args(argv)
    if args.pass_dir:
        return emit_exit(
            run_queue_conflict(
                pass_dir=str(args.pass_dir),
                config_path=args.config,
                live=bool(args.live),
            )
        )
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return emit_exit(err("stdin must be JSON object"))
    return emit_exit(evaluate_stdin(payload))


if __name__ == "__main__":
    raise SystemExit(main())
