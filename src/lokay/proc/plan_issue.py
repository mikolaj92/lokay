"""Atomic: write deterministic approach plan into worktree before run_agent.

Evidence for intentional issues (trust-with-evidence). Not a human gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.approach_plan import (
    APPROACH_REL_PATH,
    build_approach,
    render_approach_md,
    write_approach_file,
)
from lokay.envelope import emit_exit, err, ok
from lokay.models import Issue
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed


def _issue_from_args(args: argparse.Namespace) -> Issue:
    if args.issue_json:
        raw = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("issue-json must be an object")
        return Issue.from_dict(raw)
    if not args.repo or args.issue is None:
        raise ValueError("require --repo and --issue (or --issue-json)")
    return Issue(
        repo=str(args.repo),
        number=int(args.issue),
        title=str(args.title or ""),
        body=str(args.body or ""),
        labels=[],
        assignees=[],
        url=str(args.url or ""),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-plan-issue")
    add_config_live(p)
    p.add_argument("--worktree", required=True, help="git worktree path")
    p.add_argument("--repo", default="")
    p.add_argument("--issue", type=int, default=None)
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--url", default="")
    p.add_argument(
        "--issue-json",
        default="",
        help="path to Issue JSON object (overrides --repo/--issue/--title/--body)",
    )
    p.add_argument(
        "--rel-path",
        default=APPROACH_REL_PATH,
        help=f"approach file relative to worktree (default {APPROACH_REL_PATH})",
    )
    p.add_argument(
        "--llm",
        action="store_true",
        help="optional LLM assist (fail-closed; skipped by default — deterministic path)",
    )
    args = p.parse_args(argv)

    if args.llm:
        # Skippable slot: default path is deterministic. Requesting LLM without a
        # configured assist fails closed rather than inventing a stub planner.
        return emit_exit(
            err(
                "plan_issue llm assist not configured; omit --llm for deterministic plan",
                llm_requested=True,
            )
        )

    try:
        issue = _issue_from_args(args)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))

    worktree = Path(args.worktree)
    plan = build_approach(issue, worktree=worktree if worktree.is_dir() else None)
    content = render_approach_md(plan)
    rel = str(args.rel_path or APPROACH_REL_PATH)
    approach_path = str(worktree / rel)

    cfg = load_cfg(args) if args.live else None
    try:
        live = mutations_allowed(live_flag=args.live, cfg=cfg)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))

    wrote = False
    if live:
        if not worktree.is_dir():
            return emit_exit(err(f"worktree not found: {worktree}"))
        try:
            write_approach_file(worktree, content, rel_path=rel)
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc)))
        wrote = True

    return emit_exit(
        ok(
            planned=not live,
            wrote=wrote,
            repo=issue.repo,
            issue=issue.number,
            worktree=str(worktree),
            approach_path=approach_path,
            approach_rel=rel,
            source=plan.source,
            plan=plan.to_dict(),
            content=content,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
