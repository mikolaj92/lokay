"""One job: record issue-to-PR cycle start as a JSON receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok


def default_cycle_dir() -> Path:
    return Path.home() / ".lokay" / "cycle"


def parse_repo(repo: str) -> tuple[str, str]:
    parts = str(repo).strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repo must be owner/name")
    return parts[0], parts[1]


def cycle_receipt_path(cycle_dir: Path, repo: str, issue: int) -> Path:
    owner, name = parse_repo(repo)
    return cycle_dir / f"{owner}__{name}__{int(issue)}.json"


def run_cycle_start(
    *,
    repo: str,
    issue: int,
    cycle_dir: Path | str | None = None,
) -> dict[str, Any]:
    try:
        n = int(issue)
    except (TypeError, ValueError):
        return err("issue must be an integer")
    if n < 1:
        return err("issue must be a positive integer")
    try:
        parse_repo(repo)
    except ValueError as exc:
        return err(str(exc))

    dest = Path(cycle_dir).expanduser() if cycle_dir else default_cycle_dir()
    path = cycle_receipt_path(dest, repo, n)
    started_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"repo": str(repo).strip(), "issue": n, "started_ts": started_ts}
    try:
        dest.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return err(str(exc), repo=str(repo).strip(), issue=n, path=str(path))
    return ok(repo=payload["repo"], issue=n, started_ts=started_ts, path=str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-cycle-start")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument(
        "--dir",
        default="",
        help="receipt directory (default ~/.lokay/cycle)",
    )
    args = parser.parse_args(argv)
    dest = str(args.dir).strip() or None
    return emit_exit(run_cycle_start(repo=args.repo, issue=int(args.issue), cycle_dir=dest))


if __name__ == "__main__":
    raise SystemExit(main())
