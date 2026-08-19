"""One job: retire a ready issue already delivered by a merged closing PR."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.gh_prs import find_pr_fixing_issue
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def run_closeout(
    *, repo: str, issue: int, config_path: str | None, live: bool
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    pull = find_pr_fixing_issue(
        runner(cfg), repo, issue, live=allowed, merged_only=True
    )
    if pull is None:
        return ok(repo=repo, issue=issue, delivered=False, labels_removed=False)

    argv = ["--repo", repo, "--issue", str(issue)]
    if not allowed:
        argv.append("--dry-run")
    parked = run_proc(p_park.main, argv)
    return ok(
        repo=repo,
        issue=issue,
        pr=pull.get("number"),
        delivered=True,
        labels_removed=bool(parked.get("ok") and parked.get("removed")),
        parked=parked,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-closeout")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True, type=int)
    args = parser.parse_args(argv)
    return emit_exit(
        run_closeout(
            repo=str(args.repo),
            issue=int(args.issue),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
