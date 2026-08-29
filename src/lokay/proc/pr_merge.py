"""Atomic: merge PR (no force/admin)."""

from __future__ import annotations

import argparse

from lokay.code import load_code, slot_from_repo
from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-merge")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--issue", type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    if live and not cfg.merge_enabled:
        return emit_exit(err("merge.enabled is false in config", planned=True))
    repos = list(getattr(cfg, "repos", None) or [])
    repo = next((r for r in repos if getattr(r, "name", None) == args.repo), None)
    if repo is None:
        from pathlib import Path

        root = getattr(cfg, "worktrees_root", None)
        repo = RepoConfig(name=args.repo, clone_path=Path(root or "/tmp") / "unused")
    try:
        contract = load_code(slot_from_repo(repo), runner=runner(), config=cfg, live=live)
        contract.pr.merge_commit(args.pr)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    parked = None
    if live and args.issue is not None:
        parked = run_proc(
            unbounded_park.main,
            [
                *(["--config", args.config] if args.config else []),
                "--live",
                "--repo",
                args.repo,
                "--issue",
                str(args.issue),
            ],
        )
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            pr=args.pr,
            merged=live,
            issue=args.issue,
            parked=parked,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
