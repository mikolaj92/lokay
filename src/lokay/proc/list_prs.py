"""Atomic: list open ai/fix/* PRs. Read-only; network by default."""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import list_open_ai_prs
from lokay.proc._common import add_config_read, load_cfg, read_live, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-list-prs")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        repo = RepoConfig(name=args.repo, clone_path=cfg.worktrees_root / "unused")
    try:
        prs = list_open_ai_prs(runner(), cfg, repo, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(offline=not live, repo=args.repo, prs=[x.to_dict() for x in prs], count=len(prs))
    )


if __name__ == "__main__":
    raise SystemExit(main())
