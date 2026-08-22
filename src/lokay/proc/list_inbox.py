"""Atomic: list undecided open issues (inbox) for one repo → JSON. Read-only."""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_inbox_issues
from lokay.proc._common import add_config_read, load_cfg, read_live, runner
from lokay.stuck import is_blocked_in_ledger, load_stuck, stuck_path_for


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-list-inbox")
    add_config_read(p)
    p.add_argument("--repo", required=True, help="owner/name")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(offline=not live, repo=args.repo, issues=[], count=0, actions=[])
        )
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        repo = RepoConfig(name=args.repo, clone_path=cfg.worktrees_root / "unused")
    try:
        # Inbox rate limit does not stamp empty.
        issues = list_inbox_issues(
            runner(cfg), cfg, repo, live=live
        )
        stuck = load_stuck(stuck_path_for(cfg.state_path))
        inbox = []
        blocked_numbers: list[int] = []
        for issue in issues:
            if is_blocked_in_ledger(stuck, args.repo, issue.number):
                blocked_numbers.append(issue.number)
                continue
            inbox.append(issue)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), repo=args.repo))
    actions: list[dict[str, object]] = []
    if blocked_numbers:
        actions.append(
            {
                "step": "skip_inbox_stuck_blocked",
                "repo": args.repo,
                "issues": blocked_numbers,
            }
        )
    return emit_exit(
        ok(
            offline=not live,
            repo=args.repo,
            issues=[i.to_dict() for i in inbox],
            count=len(inbox),
            actions=actions,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
