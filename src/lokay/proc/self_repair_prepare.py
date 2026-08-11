"""Atomic: prepare an isolated recovery worktree at exact origin/main."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec

REPO = "mikolaj92/lokay"


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
        if worktree.exists():
            run.run(
                git_spec(["worktree", "remove", "--force", str(worktree)], cwd=repo.clone_path),
                live=True,
            )
            shutil.rmtree(worktree, ignore_errors=True)
            run.run(git_spec(["worktree", "prune"], cwd=repo.clone_path), live=True)
        base = run.run_checked(
            git_spec(["rev-parse", "origin/main"], cwd=repo.clone_path), live=True
        ).stdout.strip()
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
