"""One job: park leftover ready labels on a delivered mill issue."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.gh_issues import is_github_rate_limit_error
from lokay.gh_prs import find_pr_fixing_issue
from lokay.gh_rate import parse_survey_list, survey_list_cap
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import gh_spec

WORK_READY_LABEL = "work:ready"
LEFTOVER_TTL_SECONDS = 300
LEFTOVER_STAMP_NAME = "leftover-closeout.stamp"


def _park_ready(
    *, repo: str, issue: int, allowed: bool, config_path: str | None = None
) -> dict[str, Any]:
    argv = [
        *(["--config", config_path] if config_path else []),
        "--repo",
        repo,
        "--issue",
        str(issue),
    ]
    argv.append("--live" if allowed else "--dry-run")
    return run_proc(p_park.main, argv)


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
    parked = _park_ready(
        repo=repo, issue=issue, allowed=allowed, config_path=config_path
    )
    return ok(
        repo=repo,
        issue=issue,
        pr=pull.get("number"),
        delivered=True,
        labels_removed=bool(parked.get("ok") and parked.get("removed")),
        parked=parked,
    )


def leftover_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / LEFTOVER_STAMP_NAME


def mill_leftover_stamp_path() -> Path:
    """Operator mill leftover stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / LEFTOVER_STAMP_NAME


def _is_operator_mill_leftover_stamp(stamp: Path) -> bool:
    mill = mill_leftover_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def leftover_recently_empty(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip leftover GitHub lists using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_leftover_stamp(
        stamp
    ):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < LEFTOVER_TTL_SECONDS


def _touch_leftover_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_leftover_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def closed_ready_numbers(
    issue_runner: Any, repo: str, label: str, *, live: bool
) -> list[int]:
    if not live or not label:
        return []
    cap = survey_list_cap()
    result = issue_runner.run_checked(
        gh_spec(
            [
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                "closed",
                "--label",
                label,
                "--json",
                "number,state",
                "--limit",
                str(cap),
            ],
            timeout_seconds=60,
        ),
        live=live,
    )
    # Leftover-closeout refuses a silently truncated CLOSED issue list.
    rows = parse_survey_list(result.stdout, kind="closed-ready", repo=repo, cap=cap)
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
    """Invoke the authored leftover-closeout Fala."""
    from lokay.proc.leftover_closeout_subflow import run

    return run(config_path=config_path, live=live)


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
