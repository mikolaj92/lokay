"""Atomic: close a PR (e.g. merge conflicts). Mutates only with --live."""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.source import load_code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-close")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument(
        "--comment",
        default="",
        help="optional comment explaining why the PR is closed",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args) if args.live else None
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    repo = None
    if cfg is not None:
        repos = list(getattr(cfg, "repos", None) or [])
        repo = next((r for r in repos if getattr(r, "name", None) == args.repo), None)
    if repo is None:
        from pathlib import Path

        from lokay.config import Config

        if cfg is None:
            cfg = Config()
        root = getattr(cfg, "worktrees_root", None)
        repo = RepoConfig(name=args.repo, clone_path=Path(root or "/tmp") / "unused")
    try:
        contract = load_code(repo, runner=runner(), config=cfg, live=live)
        contract.pr.close(int(args.pr), comment=str(args.comment or ""))  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            pr=int(args.pr),
            closed=live,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
