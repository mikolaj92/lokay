"""One job: drop leftover worktrees that cannot resume.

After occupancy is known, a merged or closed-CONFLICTING corner still
occupies disk (Mini: ~158G). KEEP a live i2pr (whole repo), a repo whose PR survey failed,
an open covering PR, or an unpublished timeout leftover. A ready
published tip is stale — issue_to_pr RESETs from ``origin/main`` — unless it
contains real uncommitted timeout work. REMOVE only fully classified clean
leftovers. A failed ``list_prs`` is unknown, not idle.
Never force-push. Fetch flake / unreadable git is fail-closed KEEP.
Classify with one ``ls-remote`` per repo. Never fetch here: a 300s
``git fetch`` per leftover repo eats the 5–10 min cycle. Walk only
survey_scope (hot + rotated cold). Cap leftover classification per pass
(``CLASSIFY_CAP``): ``leftover_status`` (rev-list + ls-files) on 66
corners ate the implement slot. A fat set instead checks at most the oldest
four issues and removes only corners whose issues are CLOSED.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import classify_changed_paths, list_uncommitted_paths
from lokay.git_worktree import (
    iter_worktrees,
    leftover_status,
    remote_heads,
    remove_worktree,
)
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc._common import (
    add_config_live,
    load_cfg,
    mutations_allowed,
    runner as make_runner,
)
from lokay.proc.detach_issue_to_pr import (
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)
from lokay.runner import Runner, git_spec
from lokay.stuck import issue_number_from_branch

# leftover_status is seconds each (rev-list + ls-files). 66 leftovers
# ate the 5–10 min implement slot. Classify a handful; skip the rest.
CLASSIFY_CAP = 4
OVER_CAP_TTL_SECONDS = 300
IDLE_OVER_CAP_TTL_SECONDS = 900
OVER_CAP_STAMP_NAME = "reap-over-cap.stamp"

# The mini mill only delivers Lokay. Product repositories can remain in the
# shared catalog, but this atom must not inspect or classify their worktrees.


def over_cap_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / OVER_CAP_STAMP_NAME


def mill_over_cap_stamp_path() -> Path:
    """Operator mill over-cap stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / OVER_CAP_STAMP_NAME


def _is_operator_mill_over_cap_stamp(stamp: Path) -> bool:
    mill = mill_over_cap_stamp_path()
    try:
        return stamp.expanduser().resolve() == mill.resolve()
    except OSError:
        return stamp.expanduser() == mill


def over_cap_recently_idle(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    # Pytest must not skip over-cap GitHub views using the mill stamp.
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_mill_over_cap_stamp(
        stamp
    ):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    limit = OVER_CAP_TTL_SECONDS if ttl is None else ttl
    return 0 <= age < limit


def _touch_over_cap_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_over_cap_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def _issue_is_closed(repo: str, issue: int) -> bool | None:
    """Return issue closure without doing the expensive git classification."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue),
                "--repo",
                repo,
                "--json",
                "state",
                "--jq",
                ".state",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    state = result.stdout.strip().upper()
    return state == "CLOSED" if state in {"OPEN", "CLOSED"} else None


def _oldest(leftovers: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    def modified(item: tuple[Path, str]) -> float:
        try:
            return item[0].stat().st_mtime
        except OSError:
            return float("inf")

    return sorted(leftovers, key=modified)


def _oldest_issued(
    leftovers: list[tuple[Path, str]], *, branch_prefix: str
) -> list[tuple[Path, str]]:
    """Idle CLASSIFY_CAP skips no-issue leftovers so Fala cannot starve mill issues.

    Harvest leftovers are not mill issues.
    """
    issued = [
        item
        for item in leftovers
        if issue_number_from_branch(item[1], branch_prefix=branch_prefix) is not None
    ]
    return _oldest(issued)


def _oldest_issued_clean(
    leftovers: list[tuple[Path, str]], *, branch_prefix: str
) -> list[tuple[Path, str]]:
    """Idle CLASSIFY_CAP skips dirty-real leftovers so KEEP cannot starve mill issues."""
    issued = _oldest_issued(leftovers, branch_prefix=branch_prefix)
    git = Runner()
    clean: list[tuple[Path, str]] = []
    for path, branch in issued:
        if len(clean) >= CLASSIFY_CAP:
            break
        try:
            kind = classify_changed_paths(list_uncommitted_paths(git, path))
        except (OSError, RuntimeError):
            continue
        if kind == "real":
            continue
        clean.append((path, branch))
    return clean


def _oldest_empty_no_issue(
    leftovers: list[tuple[Path, str]], *, branch_prefix: str
) -> list[tuple[Path, str]]:
    """Idle CLASSIFY_CAP reaps empty no-issue leftovers so harvest leftovers cannot freeze mill porcelain."""
    no_issue = [
        item
        for item in leftovers
        if issue_number_from_branch(item[1], branch_prefix=branch_prefix) is None
    ]
    git = Runner()
    empty: list[tuple[Path, str]] = []
    for path, branch in _oldest(no_issue):
        if len(empty) >= CLASSIFY_CAP:
            break
        try:
            kind = classify_changed_paths(list_uncommitted_paths(git, path))
        except (OSError, RuntimeError):
            continue
        if kind != "empty":
            continue
        empty.append((path, branch))
    return empty


def _live_keys(rows: list[dict[str, Any]]) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for row in rows:
        repo = str(row.get("repo") or "")
        try:
            issue = int(row["issue"])
        except (KeyError, TypeError, ValueError):
            continue
        if repo:
            keys.add((repo, issue))
    return keys


def _names(working: dict[str, Any], key: str) -> set[str]:
    return {str(name) for name in list(working.get(key) or []) if str(name or "")}


def _covering(
    working: dict[str, Any], *, branch_prefix: str
) -> tuple[dict[str, set[int]], dict[str, set[str]]]:
    issues: dict[str, set[int]] = {}
    heads: dict[str, set[str]] = {}
    for repo_name, prs in dict(working.get("prs_by_repo") or {}).items():
        repo_issues: set[int] = set()
        repo_heads: set[str] = set()
        for pr in list(prs or []):
            head = str(pr.get("head_ref") or "")
            if head:
                repo_heads.add(head)
            n = issue_number_from_branch(head, branch_prefix=branch_prefix)
            if n is not None:
                repo_issues.add(n)
        issues[str(repo_name)] = repo_issues
        heads[str(repo_name)] = repo_heads
    return issues, heads


def _keep_reason(
    *,
    repo: str,
    branch: str,
    issue: int | None,
    live: set[tuple[str, int]],
    live_repos: set[str],
    covered: set[int],
    heads: set[str],
) -> str | None:
    if repo in live_repos or (issue is not None and (repo, issue) in live):
        return "live_issue_to_pr"
    if issue is not None and issue in covered:
        return "covering_pr"
    if branch in heads:
        return "covering_pr"
    return None


def main(argv=None):
    from lokay.proc.reap_stale_worktrees_subflow import run

    parser = argparse.ArgumentParser(prog="lokay-reap-stale-worktrees")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    return emit_exit(
        run(pass_dir=str(args.pass_dir), config_path=args.config, live=bool(args.live))
    )


if __name__ == "__main__":
    raise SystemExit(main())
