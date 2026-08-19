"""CLI: run a Fala correlation path (graph order)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import describe_package, run_path


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-run-path")
    p.add_argument("--config", help="lokay config.yaml")
    p.add_argument("--path", default="issue_to_pr", help="correlation path id")
    p.add_argument("--repo", required=False, help="owner/name (required unless --describe)")
    p.add_argument("--issue", type=int, help="issue number (for issue_to_pr / issue_triage)")
    p.add_argument("--pr", type=int, help="PR number (for pr_repair)")
    p.add_argument("--branch", help="branch head ref (for pr_repair)")
    p.add_argument("--live", action="store_true")
    p.add_argument("--describe", action="store_true", help="print graph only")
    p.add_argument("--package", help="override fala package path")
    p.add_argument("--db-dir", help="journal directory for this Fala instance")
    args = p.parse_args(argv)

    if args.describe:
        return emit_exit(ok(**describe_package(args.package)))

    if not args.repo:
        return emit_exit(err("--repo is required"))
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
            )
        )
    if args.path in {"issue_to_pr", "issue_triage"} and args.issue is None:
        return emit_exit(err(f"--issue is required for {args.path}"))
    if args.path in {"pr_repair", "pr_triage"}:
        if args.pr is None:
            return emit_exit(err(f"--pr is required for {args.path}"))
        if not args.branch:
            return emit_exit(err(f"--branch is required for {args.path}"))

    try:
        result = run_path(
            path_id=args.path,
            repo=args.repo,
            issue=args.issue,
            pr=args.pr,
            branch=args.branch,
            config_path=args.config,
            live=bool(args.live),
            package_path=args.package,
            db_path=args.db_dir,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(**result) if result.get("ok") else err("fala path failed", **result))


if __name__ == "__main__":
    raise SystemExit(main())
