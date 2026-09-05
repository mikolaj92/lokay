"""Atomic: list open ai/fix/* PRs. Read-only; network by default."""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_read, load_cfg, read_live, runner
from lokay.source import load_code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-list-prs")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    repos = list(getattr(cfg, "repos", None) or [])
    repo = next((r for r in repos if getattr(r, "name", None) == args.repo), None)
    if repo is None:
        from pathlib import Path

        root = getattr(cfg, "worktrees_root", None)
        repo = RepoConfig(name=args.repo, clone_path=Path(root or "/tmp") / "unused")
    try:
        contract = load_code(repo, runner=runner(cfg), config=cfg, live=live)
        contract.pr.list_open()
        prs = contract.pr.lokay_dicts()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(offline=not live, repo=args.repo, prs=prs, count=len(prs))
    )


if __name__ == "__main__":
    raise SystemExit(main())
