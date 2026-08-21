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
from lokay.proc._common import add_config_live, load_cfg, runner as make_runner
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
OVER_CAP_STAMP_NAME = "reap-over-cap.stamp"

# The mini mill only delivers Lokay. Product repositories can remain in the
# shared catalog, but this atom must not inspect or classify their worktrees.
MINI_MILL_REPO = "mikolaj92/lokay"


def over_cap_stamp_path(cfg: Any) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    path = getattr(cfg, "state_path", None)
    if not path:
        return None
    return Path(path).expanduser().parent / OVER_CAP_STAMP_NAME


def over_cap_recently_idle(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < OVER_CAP_TTL_SECONDS


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


def run_reap_stale_worktrees(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = over_cap_stamp_path(cfg)
    skip_over_cap_github = over_cap_recently_idle(stamp)
    begin, working = load_begin_working(pass_dir)
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    receipt_state_unknown = has_unreadable_issue_to_pr_receipts()
    live_rows = live_issue_to_pr_receipts()
    live_keys = _live_keys(live_rows)
    live_repos = _names(working, "live_issue_to_pr_repos") | {
        name for name, _ in live_keys
    }
    survey_failed = _names(working, "pr_survey_failed")
    covered, heads = _covering(working, branch_prefix=cfg.branch_prefix)
    scope = survey_scope(begin)
    git = make_runner(cfg)
    kept: list[dict[str, Any]] = []
    reaped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    classified = 0

    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        if scope is not None and repo.name not in scope:
            continue
        leftovers = iter_worktrees(cfg, repo)
        if not leftovers:
            continue
        if receipt_state_unknown:
            # A malformed/unreadable receipt may be the only record of a
            # child that owns a clean, just-created worktree. Do not classify
            # or delete any corner until lifecycle state is readable again.
            for path, branch in leftovers:
                issue = issue_number_from_branch(
                    branch, branch_prefix=cfg.branch_prefix
                )
                row = {
                    "repo": repo.name,
                    "branch": branch,
                    "issue": issue,
                    "worktree": str(path),
                    "reason": "receipt_state_unknown",
                    "kept": True,
                }
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
            continue
        if repo.name in live_repos:
            for path, branch in leftovers:
                issue = issue_number_from_branch(
                    branch, branch_prefix=cfg.branch_prefix
                )
                row = {
                    "repo": repo.name,
                    "branch": branch,
                    "issue": issue,
                    "worktree": str(path),
                    "reason": "live_issue_to_pr",
                    "kept": True,
                }
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
            continue
        if repo.name in survey_failed:
            # A failed PR list is unknown, not idle. Wiping prs_by_repo to []
            # would make a published MERGEABLE tip look uncovered and a
            # later push --delete closes the GitHub PR (influenzer #326).
            for path, branch in leftovers:
                issue = issue_number_from_branch(
                    branch, branch_prefix=cfg.branch_prefix
                )
                row = {
                    "repo": repo.name,
                    "branch": branch,
                    "issue": issue,
                    "worktree": str(path),
                    "reason": "pr_survey_failed",
                    "kept": True,
                }
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
            continue
        clone = repo.clone_path
        repo_covered = covered.get(repo.name, set())
        repo_heads = heads.get(repo.name, set())
        if len(leftovers) > CLASSIFY_CAP:
            # Bound both GitHub lookups and removals. Closed issues are enough
            # evidence to drain old corners without expensive leftover_status.
            # Keep one aggregate row: a fat stack must not flood the pass
            # transcript with one keep action (and result row) per leftover.
            candidates = set(_oldest(leftovers)[:CLASSIFY_CAP])
            reaped_before = len(reaped)
            kept_over_cap = 0
            for path, branch in leftovers:
                issue = issue_number_from_branch(
                    branch, branch_prefix=cfg.branch_prefix
                )
                row: dict[str, Any] = {
                    "repo": repo.name,
                    "branch": branch,
                    "issue": issue,
                    "worktree": str(path),
                }
                protected = _keep_reason(
                    repo=repo.name,
                    branch=branch,
                    issue=issue,
                    live=live_keys,
                    live_repos=live_repos,
                    covered=repo_covered,
                    heads=repo_heads,
                )
                closed = (
                    False
                    if skip_over_cap_github
                    else _issue_is_closed(repo.name, issue)
                    if (path, branch) in candidates and issue is not None
                    else False
                )
                if protected is not None or not (live and closed):
                    kept_over_cap += 1
                    continue
                removed = remove_worktree(
                    git, clone, path, managed_root=cfg.worktrees_root
                )
                if not removed.get("ok"):
                    row.update(
                        kept=True,
                        reason="remove_failed",
                        error=removed.get("error"),
                    )
                    failed.append(row)
                    kept_over_cap += 1
                    continue
                row.update(kept=False, removed=True, reason="closed_issue")
                reaped.append(row)
                actions.append({"step": "reap_stale_worktree", **row})
            reaped_here = len(reaped) - reaped_before
            if not skip_over_cap_github:
                if reaped_here:
                    _clear_over_cap_stamp(stamp)
                else:
                    _touch_over_cap_stamp(stamp)
            summary = {
                "repo": repo.name,
                "reason": "over_cap",
                "kept": True,
                "kept_over_cap": kept_over_cap,
                "reaped": reaped_here,
                "leftover_count": len(leftovers),
            }
            if skip_over_cap_github:
                summary["skipped"] = True
                summary["skip_reason"] = "recent_over_cap"
            kept.append(summary)
            actions.append({"step": "keep_stale_worktree", **summary})
            continue
        base_ok = False
        published_heads: set[str] | None = None
        heads_checked = False
        fetch_err = "" if clone.exists() else "clone_path missing"

        for path, branch in leftovers:
            issue = issue_number_from_branch(branch, branch_prefix=cfg.branch_prefix)
            row: dict[str, Any] = {
                "repo": repo.name,
                "branch": branch,
                "issue": issue,
                "worktree": str(path),
            }
            reason = _keep_reason(
                repo=repo.name,
                branch=branch,
                issue=issue,
                live=live_keys,
                live_repos=live_repos,
                covered=repo_covered,
                heads=repo_heads,
            )
            if reason is None and live and issue is not None:
                closed = _issue_is_closed(repo.name, issue)
                if closed:
                    removed = remove_worktree(
                        git,
                        clone,
                        path,
                        managed_root=cfg.worktrees_root,
                    )
                    if not removed.get("ok"):
                        row.update(
                            kept=True,
                            reason="remove_failed",
                            error=removed.get("error"),
                        )
                        failed.append(row)
                        kept.append(row)
                        actions.append({"step": "keep_stale_worktree", **row})
                        continue
                    row.update(kept=False, removed=True, reason="closed_issue")
                    reaped.append(row)
                    actions.append({"step": "reap_stale_worktree", **row})
                    continue
            if reason is None and live and clone.exists() and not heads_checked:
                # Closed issues do not need git classification. For all other
                # leftovers, use local origin/main + one ls-remote per repo.
                published_heads = remote_heads(git, clone)
                heads_checked = True
                base_ok = published_heads is not None
                fetch_err = "" if base_ok else "cannot list origin heads"
            if reason is None and not (live and clone.exists() and base_ok):
                reason = "unreadability" if live else "planned"
                if live and fetch_err:
                    row["error"] = fetch_err
            if reason is None and classified >= CLASSIFY_CAP:
                reason = "over_cap"
            if reason is None:
                classified += 1
                status = leftover_status(
                    git,
                    path,
                    clone,
                    branch,
                    base="main",
                    fetch_base=False,
                    known_published=branch in (published_heads or set()),
                )
                row.update(
                    {
                        k: status[k]
                        for k in (
                            "ahead",
                            "behind_main",
                            "published",
                            "dirty",
                            "uncommitted",
                            "keep_unpublished",
                        )
                        if k in status
                    }
                )
                if not status.get("readable"):
                    reason = "unreadability"
                    row["error"] = status.get("error")
                elif status.get("uncommitted") == "real":
                    reason = "uncommitted_real"
                elif status.get("keep_unpublished"):
                    reason = "unpublished_or_dirty"
                else:
                    reason = "stale"
            row["reason"] = reason
            if reason != "stale":
                row["kept"] = True
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
                continue
            if not live:
                row["kept"] = True
                row["reason"] = "planned"
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
                continue
            removed = remove_worktree(
                git,
                clone,
                path,
                managed_root=cfg.worktrees_root,
            )
            if not removed.get("ok"):
                row["kept"] = True
                row["reason"] = "remove_failed"
                row["error"] = removed.get("error")
                failed.append(row)
                kept.append(row)
                actions.append({"step": "keep_stale_worktree", **row})
                continue
            if row.get("published"):
                git.run(
                    git_spec(
                        ["push", "origin", "--delete", branch],
                        cwd=clone,
                        timeout_seconds=120,
                    ),
                    live=True,
                )
            row["kept"] = False
            row["removed"] = True
            reaped.append(row)
            actions.append({"step": "reap_stale_worktree", **row})

    working["actions"] = actions
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        planned=not live,
        kept=kept,
        reaped=reaped,
        failed=failed,
        kept_count=sum(int(row.get("kept_over_cap", 1)) for row in kept),
        reaped_count=len(reaped),
        receipt_state_unknown=receipt_state_unknown,
    )


def reap_idle_closed_worktrees(*, config_path: str | None, live: bool = True) -> None:
    """Idle daemon_cycle skip still reaps CLOSED leftover mill worktrees.

    OSError cannot stall. Not-live skip does not reap. Hosted ticks still
    reap from factory_pass. Live i2pr / unreadable receipts keep. Fresh
    over-cap stamp still skips GitHub. No leftover_status and no
    push --delete on this path. Idle CLASSIFY_CAP skips no-issue leftovers
    so Fala cannot starve mill issues. Idle CLASSIFY_CAP skips dirty-real
    leftovers so KEEP cannot starve mill issues. Harvest leftovers are not
    mill issues. Idle CLASSIFY_CAP reaps empty no-issue leftovers so harvest
    leftovers cannot freeze mill porcelain.
    """
    if not live:
        return
    try:
        _reap_idle_closed_worktrees(config_path=config_path)
    except OSError:
        return


def _reap_idle_closed_worktrees(*, config_path: str | None) -> None:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    stamp = over_cap_stamp_path(cfg)
    if over_cap_recently_idle(stamp):
        return
    if has_unreadable_issue_to_pr_receipts():
        return
    live_keys = _live_keys(live_issue_to_pr_receipts())
    live_repos = {name for name, _ in live_keys}
    reaped_here = 0
    probed = False
    git = None
    for repo in cfg.active_repos():
        if repo.name != MINI_MILL_REPO:
            continue
        if repo.name in live_repos:
            return
        leftovers = iter_worktrees(cfg, repo)
        if not leftovers:
            continue
        # Idle CLASSIFY_CAP skips no-issue leftovers so Fala cannot starve mill issues.
        # Idle CLASSIFY_CAP skips dirty-real leftovers so KEEP cannot starve mill issues.
        # Harvest leftovers are not mill issues.
        # Idle CLASSIFY_CAP reaps empty no-issue leftovers so harvest leftovers cannot freeze mill porcelain.
        candidates = set(
            _oldest_issued_clean(leftovers, branch_prefix=cfg.branch_prefix)[:CLASSIFY_CAP]
        )
        empty_no_issue = set(
            _oldest_empty_no_issue(leftovers, branch_prefix=cfg.branch_prefix)[:CLASSIFY_CAP]
        )
        for path, branch in leftovers:
            if (path, branch) in empty_no_issue:
                probed = True
                if git is None:
                    git = make_runner(cfg)
                removed = remove_worktree(
                    git, repo.clone_path, path, managed_root=cfg.worktrees_root
                )
                if removed.get("ok"):
                    reaped_here += 1
                continue
            if (path, branch) not in candidates:
                continue
            issue = issue_number_from_branch(
                branch, branch_prefix=cfg.branch_prefix
            )
            if issue is None or (repo.name, issue) in live_keys:
                continue
            probed = True
            if not _issue_is_closed(repo.name, issue):
                continue
            if git is None:
                git = make_runner(cfg)
            removed = remove_worktree(
                git, repo.clone_path, path, managed_root=cfg.worktrees_root
            )
            if removed.get("ok"):
                reaped_here += 1
    if not probed:
        return
    if reaped_here:
        _clear_over_cap_stamp(stamp)
    else:
        _touch_over_cap_stamp(stamp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-reap-stale-worktrees")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_reap_stale_worktrees(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
