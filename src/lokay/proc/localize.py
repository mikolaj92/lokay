"""Atomic: localize edit paths before run_agent.

Live mode may ask the configured executor for a JSON path list; Python
validates against the tree. Fail-closed when empty. No embeddings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.envelope import emit_exit, err, ok
from lokay.localize import (
    LOCALIZE_REL_PATH,
    extract_issue_file_paths,
    has_issue_files_section,
    write_localize_file,
)
from lokay.localize_agent import build_localization_with_agent
from lokay.models import Issue
from lokay.proc._common import (
    add_config_live,
    semantic_agent_allowed,
    load_cfg,
    mutations_allowed,
    runner,
)


MINI_MILL_REPO = "mikolaj92/lokay"


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
    p.add_argument("--seed", default="", help="extra seed text")
    p.add_argument("--seed-file", default="", help="path to extra seed text file")
    p.add_argument("--checks-text", default="", help="PR checks / repair evidence text")
    p.add_argument("--checks-file", default="", help="path to checks evidence file")
    p.add_argument(
        "--extra-path",
        action="append",
        default=[],
        help="force-include path (repeatable)",
    )
    p.add_argument(
        "--rel-path",
        default=LOCALIZE_REL_PATH,
        help=f"localize artifact relative to worktree (default {LOCALIZE_REL_PATH})",
    )
    p.add_argument(
        "--max-paths",
        type=int,
        default=40,
        help="cap on returned paths (default 40)",
    )
    args = p.parse_args(argv)

    worktree = Path(args.worktree)
    try:
        issue = _issue_from_args(args)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))

    repo = issue.repo if issue is not None else str(args.repo or "")
    if repo and repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                wrote=False,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=repo,
                issue=(issue.number if issue else args.issue),
                worktree=str(worktree),
            )
        )

    seed = _seed_text(args, issue, worktree if worktree.is_dir() else Path("."))
    issue_file_paths = extract_issue_file_paths(issue.body) if issue is not None else ()
    bypass_agent = bool(
        issue is not None
        and (has_issue_files_section(issue.body) or issue_file_paths)
    )
    if not seed.strip():
        return emit_exit(
            err(
                "localize seed empty: need issue body, approach.md, checks, or --seed",
                reason="empty_seed",
                worktree=str(worktree),
            )
        )

    cfg = load_cfg(args) if args.config or args.live else None
    execute = bool(cfg and semantic_agent_allowed(cfg, live_flag=args.live))
    loc = build_localization_with_agent(
        runner=runner(cfg) if execute and cfg is not None else None,
        config=cfg,
        execute=execute,
        worktree=worktree if worktree.is_dir() else None,
        seed_text=seed,
        extra_paths=list(args.extra_path or []),
        max_paths=max(1, int(args.max_paths or 40)),
        skip_agent=bypass_agent,
    )
    if not loc.paths:
        return emit_exit(
            err(
                "localize produced no edit paths; refusing empty scope",
                reason="empty_paths",
                worktree=str(worktree),
                seed_paths=list(loc.seed_paths),
                notes=list(loc.notes),
            )
        )

    try:
        live = mutations_allowed(live_flag=args.live, cfg=cfg if args.live else None)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))

    rel = str(args.rel_path or LOCALIZE_REL_PATH)
    wrote = False
    localize_path = str(worktree / rel)
    if live:
        if not worktree.is_dir():
            return emit_exit(err(f"worktree not found: {worktree}"))
        try:
            write_localize_file(worktree, loc, rel_path=rel)
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc)))
        wrote = True

    return emit_exit(
        ok(
            planned=not live,
            wrote=wrote,
            worktree=str(worktree),
            localize_path=localize_path,
            localize_rel=rel,
            paths=list(loc.paths),
            seed_paths=list(loc.seed_paths),
            matched_tokens=list(loc.matched_tokens),
            source=loc.source,
            notes=list(loc.notes),
            semantic=loc.semantic,
            repo=(issue.repo if issue else str(args.repo or "")),
            issue=(issue.number if issue else args.issue),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
