"""Thin CLI facade for authored one mechanical intake check."""

import argparse

from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_read, read_live

_CHECKS = ("open", "superseded", "shape", "satisfied", "ambiguity", "duplicate_ai_pr")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-intake-check")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--check", required=True, choices=_CHECKS)
    p.add_argument("--merged-pr", action="append", type=int, default=[])
    p.add_argument("--tracker-done", action="store_true")
    p.add_argument("--covering-pr", action="append", default=[])
    args = p.parse_args(argv)
    try:
        from lokay.proc.intake_check_subflow import run

        out = run(
            config_path=args.config,
            live=read_live(args),
            repo=args.repo,
            issue=args.issue,
            check=args.check,
            merged_prs=args.merged_pr,
            tracker_done=args.tracker_done,
            covering_prs=args.covering_pr,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
