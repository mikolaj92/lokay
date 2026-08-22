"""Atomic: merge a GitHub PR with a merge-commit. No checks gate, no LLM review.

--live plus a healthy mill enables mutation. Otherwise the atom plans only.
Hosted merge-now merges require healthy. Planned merges do not.
--dry-run prints the gh command and does not merge.
"""

from __future__ import annotations

import argparse
import subprocess

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed

MERGE_TIMEOUT_SECONDS = 180
MINI_MILL_REPO = "mikolaj92/lokay"


def merge_argv(repo: str, pr: int) -> list[str]:
    return ["gh", "pr", "merge", str(pr), "--repo", repo, "--merge"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-merge-now")
    add_config_live(p)
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
    if repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                command=command,
                repo=repo,
                pr=pr,
            )
        )
    if args.dry_run or not args.live:
        return emit_exit(
            ok(
                planned=True,
                dry_run=bool(args.dry_run),
                merged=False,
                command=command,
                repo=repo,
                pr=pr,
            )
        )
    cfg = load_cfg(args)
    apply = mutations_allowed(live_flag=True, cfg=cfg)
    if not apply:  # pragma: no cover - mutations_allowed is fail-closed
        return emit_exit(err("live mutation blocked", command=command, repo=repo, pr=pr))
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
