"""CLI: run a Fala correlation path (graph order)."""

from __future__ import annotations

import argparse
import json

from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import describe_package, run_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-run-path")
    p.add_argument("--config", help="lokay config.yaml")
    p.add_argument("--path", default="issue_to_pr", help="correlation path id")
    p.add_argument("--repo", required=False, help="owner/name (required unless --describe)")
    p.add_argument("--issue", type=int, help="issue number (for issue_to_pr)")
    p.add_argument("--live", action="store_true")
    p.add_argument("--describe", action="store_true", help="print graph only")
    p.add_argument("--package", help="override fala package path")
    args = p.parse_args(argv)

    if args.describe:
        return emit_exit(ok(**describe_package(args.package)))

    if not args.repo:
        return emit_exit(err("--repo is required"))
    if args.path == "issue_to_pr" and args.issue is None:
        return emit_exit(err("--issue is required for issue_to_pr"))

    try:
        result = run_path(
            path_id=args.path,
            repo=args.repo,
            issue=args.issue,
            config_path=args.config,
            live=bool(args.live),
            package_path=args.package,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(**result) if result.get("ok") else err("fala path failed", **result))


if __name__ == "__main__":
    raise SystemExit(main())
