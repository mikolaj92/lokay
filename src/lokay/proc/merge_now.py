"""Atomic: merge a GitHub PR with a merge-commit. No checks gate, no LLM review."""

from __future__ import annotations

import argparse
import subprocess

from lokay.envelope import emit_exit, err, ok

MERGE_TIMEOUT_SECONDS = 180


def merge_argv(repo: str, pr: int) -> list[str]:
    return ["gh", "pr", "merge", str(pr), "--repo", repo, "--merge"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-merge-now")
    p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--pr", required=True, type=int)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the gh command; do not merge",
    )
    args = p.parse_args(argv)
    repo = str(args.repo)
    pr = int(args.pr)
    command = merge_argv(repo, pr)
    if args.dry_run:
        return emit_exit(ok(planned=True, dry_run=True, command=command, repo=repo, pr=pr))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=MERGE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return emit_exit(err(str(exc), command=command, repo=repo, pr=pr))
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        if not message:
            message = f"gh pr merge failed (exit {completed.returncode})"
        return emit_exit(
            err(
                message,
                command=command,
                repo=repo,
                pr=pr,
                returncode=completed.returncode,
            )
        )
    return emit_exit(ok(planned=False, merged=True, command=command, repo=repo, pr=pr))


if __name__ == "__main__":
    raise SystemExit(main())
