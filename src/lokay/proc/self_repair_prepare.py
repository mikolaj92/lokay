"""Atomic: prepare an isolated recovery worktree at exact origin/main."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_worktree import remove_worktree
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
        if worktree.exists():
            removed = remove_worktree(run, repo.clone_path, worktree)
            if not removed.get("ok"):
                raise RuntimeError(
                    f"self-repair worktree remove failed: {removed.get('error') or 'still exists'}"
                )
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
