"""One job: drop leftover worktrees that cannot resume.

After occupancy is known, a merged or closed-CONFLICTING corner still
occupies disk (Mini: ~158G). KEEP a live i2pr (whole repo), a repo whose PR survey failed,
an open covering PR, or an unpublished timeout leftover. A ready
published tip is stale — issue_to_pr RESETs from ``origin/main``.
REMOVE the rest. A failed ``list_prs`` is unknown, not idle.
Never force-push. Fetch flake / unreadable git is fail-closed KEEP.
Classify with one ``ls-remote`` per repo — a per-branch fetch stalls
the factory pass.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.git_worktree import (
    iter_worktrees,
    leftover_status,
    remote_heads,
    remove_worktree,
)
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc._common import add_config_live, load_cfg, runner as make_runner
from lokay.proc.detach_issue_to_pr import (
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)
from lokay.runner import git_spec
from lokay.stuck import issue_number_from_branch


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
    git = make_runner(cfg)
    kept: list[dict[str, Any]] = []
    reaped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for repo in cfg.active_repos():
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
        base_ok = False
        published_heads: set[str] | None = None
        if live and clone.exists():
            fetched = git.run(
                git_spec(["fetch", "origin", "main"], cwd=clone, timeout_seconds=300),
                live=True,
            )
            base_ok = fetched.returncode == 0
            fetch_err = (fetched.stderr or fetched.stdout or "").strip()
            if base_ok:
                published_heads = remote_heads(git, clone)
                if published_heads is None:
                    base_ok = False
                    fetch_err = "cannot list origin heads"
        else:
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
            if reason is None and not (live and clone.exists() and base_ok):
                reason = "unreadability" if live else "planned"
                if live and fetch_err:
                    row["error"] = fetch_err
            if reason is None:
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
                            "keep_unpublished",
                        )
                        if k in status
                    }
                )
                if not status.get("readable"):
                    reason = "unreadability"
                    row["error"] = status.get("error")
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
            removed = remove_worktree(git, clone, path)
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
        kept_count=len(kept),
        reaped_count=len(reaped),
        receipt_state_unknown=receipt_state_unknown,
    )


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
