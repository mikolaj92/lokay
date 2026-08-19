"""One job: retire a ready issue already delivered by a merged closing PR."""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.gh_prs import find_pr_fixing_issue
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import gh_spec

WORK_READY_LABEL = "work:ready"
MINI_MILL_REPO = "mikolaj92/lokay"


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


def closed_ready_numbers(
    issue_runner: Any, repo: str, label: str, *, live: bool
) -> list[int]:
    if repo != MINI_MILL_REPO or not live or not label:
        return []
    result = issue_runner.run_checked(
        gh_spec(
            [
                "issue", "list", "--repo", repo, "--state", "closed",
                "--label", label, "--json", "number,state", "--limit", "100",
            ],
            timeout_seconds=60,
        ),
        live=live,
    )
    rows = json.loads(result.stdout or "[]")
    if not isinstance(rows, list):
        return []
    out: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("state") or "").upper() != "CLOSED":
            continue
        number = int(row.get("number") or 0)
        if number > 0:
            out.append(number)
    return out


def run_closeout_leftover(*, config_path: str | None, live: bool) -> dict[str, Any]:
    """Strip leftover ready labels on CLOSED issues that already have a merged PR."""
    cfg = load_cfg(argparse.Namespace(config=config_path))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    issue_runner = runner(cfg)
    labels = [WORK_READY_LABEL]
    ready = str(getattr(cfg, "ready_label", "") or "")
    if ready and ready not in labels:
        labels.append(ready)
    closed_out: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for repo in list(cfg.repos or []):
        name = str(repo.name)
        if name != MINI_MILL_REPO:
            continue
        for label in labels:
            for number in closed_ready_numbers(issue_runner, name, label, live=allowed):
                key = (name, number)
                if key in seen:
                    continue
                seen.add(key)
                out = run_closeout(
                    repo=name, issue=number, config_path=config_path, live=live
                )
                if out.get("labels_removed"):
                    closed_out.append({"repo": name, "issue": number, "pr": out.get("pr")})
    return ok(
        leftover_closed=len(closed_out),
        labels_removed=bool(closed_out),
        issue_to_pr_started=0,
        closed_out=closed_out,
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
