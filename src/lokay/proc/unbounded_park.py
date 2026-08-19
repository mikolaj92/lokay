"""Atomic: park an unbounded issue by removing work:ready and ai:ready.

Mill will not sit a Pi on an issue that is no longer ready.
--dry-run prints the gh command and does not mutate.
Fail-closed if repo or issue is missing.
"""

from __future__ import annotations

import argparse
import subprocess
from typing import Sequence

from lokay.envelope import emit_exit, err, ok
from lokay.safety import validate_argv

READY_LABEL = "ai:ready"
WORK_READY_LABEL = "work:ready"
MINI_MILL_REPO = "mikolaj92/lokay"


def park_argv(repo: str, issue: int) -> list[str]:
    return [
        "gh",
        "issue",
        "edit",
        str(issue),
        "--repo",
        repo,
        "--remove-label",
        WORK_READY_LABEL,
        "--remove-label",
        READY_LABEL,
    ]


def parse_target(repo: str | None, issue: int | None) -> tuple[str, int] | str:
    """Return (repo, issue) or an error message. Fail-closed on missing target."""
    name = str(repo or "").strip()
    if not name:
        return "repo required (owner/name)"
    parts = name.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "repo must be owner/name"
    if issue is None:
        return "issue required"
    number = int(issue)
    if number < 1:
        return "issue must be a positive integer"
    return name, number


def run_gh(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    validate_argv(argv)
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(list(argv), 127, stdout="", stderr=str(exc))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-unbounded-park")
    p.add_argument("--repo", help="GitHub repo owner/name")
    p.add_argument("--issue", type=int, help="issue number")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the gh command and do not mutate",
    )
    args = p.parse_args(argv)
    parsed = parse_target(args.repo, args.issue)
    if isinstance(parsed, str):
        return emit_exit(err(parsed))
    repo, issue = parsed
    if repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                dry_run=bool(args.dry_run),
                planned=False,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                applied=False,
                removed=False,
                repo=repo,
                issue=issue,
                label=READY_LABEL,
            )
        )
    command = park_argv(repo, issue)
    display = " ".join(command)
    if args.dry_run:
        return emit_exit(
            ok(
                dry_run=True,
                planned=True,
                applied=False,
                removed=False,
                repo=repo,
                issue=issue,
                label=READY_LABEL,
                command=display,
                argv=command,
            )
        )
    result = run_gh(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return emit_exit(
            err(
                f"issue not found or gh failed: {repo}#{issue}",
                repo=repo,
                issue=issue,
                command=display,
                returncode=result.returncode,
                stderr=detail,
            )
        )
    return emit_exit(
        ok(
            dry_run=False,
            planned=False,
            applied=True,
            removed=True,
            repo=repo,
            issue=issue,
            label=READY_LABEL,
            command=display,
            argv=command,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
