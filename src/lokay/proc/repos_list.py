"""Atomic: list configured repos (enabled + disabled) as JSON."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config, load_cfg


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-repos")
    add_config(p)
    p.add_argument(
        "--all",
        action="store_true",
        help="include disabled repos (default: enabled only)",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    rows = []
    for repo in cfg.repos if args.all else cfg.active_repos():
        rows.append(
            {
                "name": repo.name,
                "clone_path": str(repo.clone_path),
                "priority": repo.priority,
                "enabled": repo.enabled,
                "clone_exists": repo.clone_path.exists(),
                "note": repo.note or None,
            }
        )
    return emit_exit(
        ok(
            count=len(rows),
            enabled=sum(1 for r in cfg.repos if r.enabled),
            disabled=sum(1 for r in cfg.repos if not r.enabled),
            repos=rows,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
