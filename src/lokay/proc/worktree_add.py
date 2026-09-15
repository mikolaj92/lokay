"""Atomic: ensure git worktree for branch.

Always succeeds. Fala unblocks children of a failed atom, so `ok=false`
cannot stop plan/localize/coding. `route=ready` continues; `route=missing`
means no local clone or the worktree could not be created.
"""

from __future__ import annotations

import argparse
import re
from importlib import import_module
from pathlib import Path
from typing import Any

from lokay.code.github import InvalidBranchRef
from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec
from lokay.source import load_code


def verify_repair_start_identity(
    command_runner: Any,
    *,
    repo: str,
    pr: int,
    worktree: Path,
    expected_head_sha: str,
) -> dict[str, Any]:
    """Authorize repair edits only on the recorded remote PR and local head."""
    gh_prs = import_module("lokay." + "gh_prs")

    remote = ""
    expected = str(expected_head_sha or "").lower()
    if not re.fullmatch(r"[a-f0-9]{40}", expected):
        return {"ok": True, "route": "missing", "reason": "repair_start_head_missing"}
    try:
        pr_view = gh_prs.gh_json(
            command_runner,
            ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid,headRepository"],
            live=True,
        )
        remote = str(pr_view.get("headRefOid") or "").lower()
        head_repository = pr_view.get("headRepository")
        head_repo = (
            str(head_repository.get("nameWithOwner") or "")
            if isinstance(head_repository, dict)
            else ""
        )
        if not head_repo:
            raise ValueError("PR head repository identity is missing")
        if head_repo.lower() != repo.lower():
            return {
                "ok": True,
                "route": "missing",
                "reason": "fork_hosted_repair_unsupported",
                "expected_head_sha": expected,
                "remote_head_sha": remote,
                "head_repo": head_repo,
                "worktree_head_sha": "",
            }
        if not re.fullmatch(r"[a-f0-9]{40}", remote) or remote != expected:
            return {
                "ok": True, "route": "missing",
                "reason": "repair_start_head_mismatch",
                "expected_head_sha": expected, "remote_head_sha": remote,
                "worktree_head_sha": "",
            }
        local_result = command_runner.run(
            git_spec(["rev-parse", "--verify", "HEAD^{commit}"], cwd=worktree, timeout_seconds=30),
            live=True,
        )
        local = str(local_result.stdout or "").strip().lower()
        clean = command_runner.run(
            git_spec(
                ["status", "--porcelain=v1", "--untracked-files=all"],
                cwd=worktree,
                timeout_seconds=30,
            ),
            live=True,
        )
    except Exception:
        return {
            "ok": True, "route": "missing",
            "reason": "repair_start_identity_unavailable",
            "expected_head_sha": expected, "remote_head_sha": remote,
            "worktree_head_sha": "",
        }
    if (
        remote != expected
        or local != expected
        or not re.fullmatch(r"[a-f0-9]{40}", local)
        or local_result.returncode != 0
        or clean.returncode != 0
        or (local_result.stderr or "").strip()
        or (clean.stdout or "").strip()
        or (clean.stderr or "").strip()
    ):
        return {
            "ok": True,
            "route": "missing",
            "reason": "repair_start_head_mismatch",
            "expected_head_sha": expected,
            "remote_head_sha": remote,
            "worktree_head_sha": local,
        }
    return {
        "ok": True,
        "route": "ready",
        "repair_start_head_sha": expected,
        "worktree_head_sha": local,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-worktree-add")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--base", default="main")
    p.add_argument(
        "--reset-base",
        action="store_true",
        help="recreate branch/worktree from origin/<base> (issue_to_pr re-implement)",
    )
    p.add_argument("--pr", type=int, help="PR identity for exact-head repair preflight")
    p.add_argument("--repair-start-head-sha", default="")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        return emit_exit(
            ok(
                route="missing",
                reason="repo_not_in_config",
                error=f"repo not in config: {args.repo}",
                repo=args.repo,
                branch=args.branch,
            )
        )
    if not repo.clone_path.exists():
        return emit_exit(
            ok(
                route="missing",
                reason="clone_path_missing",
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
                planned=not mutations_allowed(live_flag=args.live, cfg=cfg),
            )
        )
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    repair_start_sha = str(args.repair_start_head_sha or "").lower()
    if repair_start_sha and (args.pr is None or not re.fullmatch(r"[a-f0-9]{40}", repair_start_sha)):
        return emit_exit(ok(
            route="missing",
            reason="repair_start_pr_missing" if args.pr is None else "repair_start_head_missing",
            repo=args.repo, branch=args.branch, pr=args.pr,
        ))
    if repair_start_sha and not live:
        return emit_exit(ok(
            route="missing", reason="repair_start_unverified_offline",
            repo=args.repo, pr=args.pr, branch=args.branch,
            repair_start_head_sha=repair_start_sha,
        ))
    try:
        command_runner = runner()
        if repair_start_sha:
            if not live:
                return emit_exit(ok(
                    route="missing", reason="repair_start_unverified_offline",
                    repo=args.repo, pr=args.pr, branch=args.branch,
                    repair_start_head_sha=repair_start_sha,
                ))
            ensure_repair_worktree = import_module(
                "lokay." + "git_worktree"
            ).ensure_repair_worktree
            gh_prs = import_module("lokay." + "gh_prs")
            head_view = gh_prs.gh_json(
                command_runner,
                ["pr", "view", str(args.pr), "--repo", args.repo, "--json", "headRepository"],
                live=True,
            )
            head_repository = head_view.get("headRepository")
            head_repo = (
                str(head_repository.get("nameWithOwner") or "")
                if isinstance(head_repository, dict)
                else ""
            )
            if head_repo.lower() != args.repo.lower():
                return emit_exit(ok(
                    route="missing", reason="fork_hosted_repair_unsupported",
                    repo=args.repo, pr=args.pr, branch=args.branch,
                    head_repo=head_repo, repair_start_head_sha=repair_start_sha,
                ))
            path = ensure_repair_worktree(
                command_runner, cfg, repo, args.branch, repair_start_sha,
                head_repo=head_repo, live=True,
            )
        else:
            contract = load_code(repo, runner=command_runner, config=cfg, live=live)
            path = contract.repo.worktree(
                args.branch, base=args.base, reset_to_base=bool(args.reset_base)
            )
        if repair_start_sha:
            identity = verify_repair_start_identity(
                command_runner, repo=args.repo, pr=args.pr, worktree=path,
                expected_head_sha=repair_start_sha,
            )
            if identity.get("route") != "ready":
                return emit_exit(ok(
                    **{key: value for key, value in identity.items() if key != "route"},
                    route="missing", repo=args.repo, pr=args.pr, branch=args.branch,
                    worktree=str(path),
                ))
            identity = {
                "worktree_head_sha": identity["worktree_head_sha"],
                "verified_repair_start_head_sha": identity["repair_start_head_sha"],
            }
    except InvalidBranchRef as exc:
        return emit_exit(
            ok(
                route="missing",
                reason=exc.reason,
                error=str(exc),
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(
            ok(
                route="missing",
                reason="worktree_failed",
                error=str(exc),
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
            )
        )
    return emit_exit(
        ok(
            route="ready",
            planned=not live,
            repo=args.repo,
            branch=args.branch,
            worktree=str(path),
            pr=args.pr,
            **({
                "repair_start_head_sha": identity["verified_repair_start_head_sha"],
                "worktree_head_sha": identity["worktree_head_sha"],
            } if repair_start_sha else {
                "repair_start_head_sha": str(args.repair_start_head_sha or "").lower(),
            }),
            reset_to_base=bool(args.reset_base),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
