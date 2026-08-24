"""Atomic: localize edit paths before run_agent.

Live mode may ask the configured executor for a JSON path list; Python
validates against the tree. Fail-closed when empty. No embeddings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.envelope import emit_exit, err
from lokay.localize import (
    LOCALIZE_REL_PATH,
)
from lokay.models import Issue
from lokay.proc._common import (
    add_config_live,
)


def _issue_from_args(args: argparse.Namespace) -> Issue | None:
    if args.issue_json:
        raw = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("issue-json must be an object")
        return Issue.from_dict(raw)
    if args.repo and args.issue is not None:
        return Issue(
            repo=str(args.repo),
            number=int(args.issue),
            title=str(args.title or ""),
            body=str(args.body or ""),
            labels=[],
            assignees=[],
            url=str(args.url or ""),
        )
    return None


def _seed_text(args: argparse.Namespace, issue: Issue | None, worktree: Path) -> str:
    chunks: list[str] = []
    if args.seed_file:
        chunks.append(Path(args.seed_file).read_text(encoding="utf-8"))
    if args.seed:
        chunks.append(str(args.seed))
    if issue is not None:
        chunks.append(f"{issue.title or ''}\n{issue.body or ''}")
    approach = worktree / APPROACH_REL_PATH
    if approach.is_file():
        chunks.append(approach.read_text(encoding="utf-8"))
    if args.checks_text:
        chunks.append(str(args.checks_text))
    if args.checks_file:
        chunks.append(Path(args.checks_file).read_text(encoding="utf-8"))
    return "\n\n".join(c for c in chunks if c and str(c).strip())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-localize")
    add_config_live(p)
    p.add_argument("--worktree", required=True)
    p.add_argument("--repo", default="")
    p.add_argument("--issue", type=int)
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--url", default="")
    p.add_argument("--issue-json", default="")
    p.add_argument("--seed", default="")
    p.add_argument("--seed-file", default="")
    p.add_argument("--checks-text", default="")
    p.add_argument("--checks-file", default="")
    p.add_argument("--extra-path", action="append", default=[])
    p.add_argument("--rel-path", default=LOCALIZE_REL_PATH)
    p.add_argument("--max-paths", type=int, default=40)
    args = p.parse_args(argv)
    try:
        issue = _issue_from_args(args)
        issue_raw = (
            issue.to_dict()
            if issue
            else {
                "repo": args.repo,
                "number": args.issue or 0,
                "title": args.title,
                "body": args.body,
                "url": args.url,
            }
        )
        seed_parts = [args.seed]
        if args.seed_file:
            seed_parts.append(Path(args.seed_file).read_text(encoding="utf-8"))
        if args.checks_file:
            seed_parts.append(Path(args.checks_file).read_text(encoding="utf-8"))
        checks = "\n\n".join(x for x in [args.checks_text, *seed_parts] if x)
        from lokay.proc.localize_execution_subflow import run

        out = run(
            config_path=args.config,
            live=bool(args.live),
            extra_inputs={
                "worktree": args.worktree,
                "repo": args.repo,
                "issue_raw": issue_raw,
                "plan": {},
                "checks_text": checks,
                "review": {},
                "extra_paths": args.extra_path,
                "max_paths": args.max_paths,
                "rel_path": args.rel_path,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
