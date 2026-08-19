"""Atomic: list ready issues for one repo → JSON. Read-only; network by default."""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_issues_with_label, list_ready_issues
from lokay.proc._common import add_config_read, load_cfg, read_live, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-list-issues")
    add_config_read(p)
    p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--label", help="list issues carrying this label")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        repo = RepoConfig(name=args.repo, clone_path=cfg.worktrees_root / "unused")
    try:
        issue_runner = runner(cfg)
        if args.label:
            issues = list_issues_with_label(
                issue_runner, cfg, repo, label=args.label, live=live
            )
        else:
            issues = list_ready_issues(issue_runner, cfg, repo, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), repo=args.repo))
    return emit_exit(
        ok(
            offline=not live,
            repo=args.repo,
            issues=[i.to_dict() for i in issues],
            count=len(issues),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
