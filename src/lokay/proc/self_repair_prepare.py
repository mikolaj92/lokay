"""Prepare or safely resume an isolated recovery worktree."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import classify_changed_paths, list_uncommitted_paths
from lokay.git_worktree import remove_worktree, worktree_owned_by_clone
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec

REPO = "mikolaj92/lokay"


def published_self_repair_commit(*, clone: Path, fingerprint: str, run) -> str:
    """Return origin/main SHA that already contains this fingerprint, or ''."""
    needle = f"self-repair: {fingerprint}"
    listed = run.run(
        git_spec(
            ["log", "origin/main", "--grep", needle, "-1", "--format=%H"],
            cwd=clone,
            timeout_seconds=60,
        ),
        live=True,
    )
    sha = (listed.stdout or "").strip().splitlines()
    return sha[0] if sha and len(sha[0]) >= 7 else ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-prepare")
    add_config_live(p)
    p.add_argument("--fingerprint", required=True)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    repo = next((r for r in cfg.active_repos() if r.name == REPO), None)
    if repo is None:
        return emit_exit(err("canonical Lokay checkout unavailable"))
    worktree = cfg.worktrees_root / "_self_repair" / args.fingerprint
    if not live:
        return emit_exit(ok(planned=True, worktree=str(worktree), base_sha=""))
    run = runner()
    try:
        origin = run.run_checked(
            git_spec(["remote", "get-url", "origin"], cwd=repo.clone_path), live=True
        ).stdout.strip().removesuffix(".git")
        if origin not in {
            "https://github.com/mikolaj92/lokay",
            "git@github.com:mikolaj92/lokay",
        }:
            raise RuntimeError("canonical Lokay origin mismatch")
        run.run_checked(
            git_spec(["fetch", "origin", "main"], cwd=repo.clone_path, timeout_seconds=300),
            live=True,
        )
        existing = published_self_repair_commit(
            clone=repo.clone_path, fingerprint=args.fingerprint, run=run
        )
        if existing:
            return emit_exit(
                ok(
                    planned=False,
                    repo=REPO,
                    worktree="",
                    base_sha=existing,
                    commit=existing,
                    already_on_main=True,
                )
            )
        base = run.run_checked(
            git_spec(["rev-parse", "origin/main"], cwd=repo.clone_path), live=True
        ).stdout.strip()
        resumed = False
        if worktree.exists():
            owned = worktree_owned_by_clone(run, repo.clone_path, worktree)
            if owned is not True:
                detail = "unreadable" if owned is None else "not owned by canonical clone"
                raise RuntimeError(f"cannot resume existing self-repair worktree: {detail}")
            uncommitted = classify_changed_paths(
                list_uncommitted_paths(run, worktree)
            )
            head = run.run_checked(
                git_spec(["rev-parse", "HEAD"], cwd=worktree, timeout_seconds=60),
                live=True,
            ).stdout.strip()
            ahead_text = run.run_checked(
                git_spec(
                    ["rev-list", "--count", f"{base}..HEAD"],
                    cwd=worktree,
                    timeout_seconds=60,
                ),
                live=True,
            ).stdout.strip()
            try:
                ahead = int(ahead_text)
            except ValueError as exc:
                raise RuntimeError(
                    f"cannot parse existing self-repair ahead count: {ahead_text!r}"
                ) from exc
            if uncommitted == "plan_only":
                raise RuntimeError(
                    "cannot resume self-repair worktree with uncommitted plan evidence"
                )
            if uncommitted == "real" and ahead != 0:
                raise RuntimeError(
                    "cannot resume dirty self-repair worktree with unrecognized commits"
                )
            if ahead > 0 and uncommitted == "empty":
                subject = run.run_checked(
                    git_spec(["log", "-1", "--format=%s"], cwd=worktree),
                    live=True,
                ).stdout.strip()
                if ahead != 1 or subject != f"self-repair: {args.fingerprint}":
                    raise RuntimeError(
                        "cannot resume unrecognized committed self-repair candidate"
                    )
            if uncommitted == "real" or ahead > 0:
                contains_base = run.run(
                    git_spec(
                        ["merge-base", "--is-ancestor", base, "HEAD"],
                        cwd=worktree,
                        timeout_seconds=60,
                    ),
                    live=True,
                )
                if contains_base.returncode != 0:
                    raise RuntimeError(
                        "cannot resume self-repair worktree outside current origin/main"
                    )
                resumed = True
                candidate_commit = head if ahead > 0 else ""
            else:
                removed = remove_worktree(
                    run,
                    repo.clone_path,
                    worktree,
                    managed_root=cfg.worktrees_root,
                )
                if not removed.get("ok"):
                    raise RuntimeError(
                        f"self-repair worktree remove failed: {removed.get('error') or 'still exists'}"
                    )
        if resumed:
            return emit_exit(
                ok(
                    planned=False,
                    repo=REPO,
                    worktree=str(worktree),
                    base_sha=base,
                    resumed=True,
                    candidate_commit=candidate_commit,
                )
            )
        worktree.parent.mkdir(parents=True, exist_ok=True)
        run.run_checked(
            git_spec(["worktree", "add", "--detach", str(worktree), base], cwd=repo.clone_path),
            live=True,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=False, repo=REPO, worktree=str(worktree), base_sha=base))


if __name__ == "__main__":
    raise SystemExit(main())
