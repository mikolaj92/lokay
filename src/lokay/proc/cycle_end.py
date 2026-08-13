"""One job: measure issue-to-PR cycle minutes from a start receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok

BUDGET_MINUTES = 10


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


def parse_ts(raw: str) -> datetime:
    text = str(raw).strip()
    if not text:
        raise ValueError("timestamp is empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def run_cycle_end(
    *,
    repo: str,
    issue: int,
    cycle_dir: Path | str | None = None,
    pr_opened_ts: str | None = None,
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
    if not path.is_file():
        return err(
            "cycle start file missing",
            repo=str(repo).strip(),
            issue=n,
            path=str(path),
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return err(str(exc), repo=str(repo).strip(), issue=n, path=str(path))
    if not isinstance(raw, dict):
        return err(
            "cycle start file must be a JSON object",
            repo=str(repo).strip(),
            issue=n,
            path=str(path),
        )
    started_raw = raw.get("started_ts")
    if started_raw is None:
        return err(
            "cycle start file missing started_ts",
            repo=str(repo).strip(),
            issue=n,
            path=str(path),
        )
    try:
        started = parse_ts(str(started_raw))
        end = parse_ts(pr_opened_ts) if pr_opened_ts else datetime.now(timezone.utc)
    except ValueError as exc:
        return err(str(exc), repo=str(repo).strip(), issue=n, path=str(path))

    minutes = max(0, int((end - started).total_seconds() // 60))
    return ok(
        repo=str(repo).strip(),
        issue=n,
        minutes=minutes,
        ok_budget=minutes <= BUDGET_MINUTES,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-cycle-end")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument(
        "--dir",
        default="",
        help="receipt directory (default ~/.lokay/cycle)",
    )
    parser.add_argument(
        "--pr-opened-ts",
        default="",
        help="PR opened timestamp (ISO UTC); default now",
    )
    args = parser.parse_args(argv)
    dest = str(args.dir).strip() or None
    opened = str(args.pr_opened_ts).strip() or None
    return emit_exit(
        run_cycle_end(
            repo=args.repo,
            issue=int(args.issue),
            cycle_dir=dest,
            pr_opened_ts=opened,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
