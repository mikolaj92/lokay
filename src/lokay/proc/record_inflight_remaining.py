"""Write last-pass remaining from this cycle's working.json (not record_pass)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.pass_receipt import read_pass_receipt, write_pass_receipt
from lokay.proc._common import add_config_live


def remaining_from_working(working: dict[str, Any]) -> dict[str, Any]:
    issues = dict(working.get("inbox_issues_by_repo") or {})
    listed = sum(len(rows or []) for rows in issues.values())
    inbox = listed if listed else int(working.get("remaining_inbox") or 0)
    ready_by = dict(working.get("ready_by_repo") or {})
    ready = sum(len(rows or []) for rows in ready_by.values()) or int(
        working.get("remaining_ready") or 0
    )
    inbox_counts = dict(working.get("inbox_by_repo") or {})
    by_repo = []
    for repo in sorted({*issues, *ready_by, *inbox_counts}):
        by_repo.append(
            {
                "repo": repo,
                "inbox": len(issues.get(repo) or []) or int(inbox_counts.get(repo) or 0),
                "ready": len(ready_by.get(repo) or []),
            }
        )
    remaining = {
        "inbox": inbox,
        "ready": ready,
        "ready_with_open_pr": int(working.get("remaining_ready_with_pr") or 0),
        "open_ai_prs": int(working.get("remaining_prs") or 0),
        "survey_errors": int(working.get("survey_errors") or 0),
        "by_repo": by_repo,
    }
    for key, value in working.items():
        if key == "leftover" or str(key).startswith("leftover_"):
            remaining[key] = value
    return remaining


def remaining_from_pass_dir(pass_dir: str | Path) -> dict[str, Any] | None:
    try:
        working = json.loads(
            (Path(pass_dir) / "working.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(working, dict):
        return None
    return remaining_from_working(working)


def remaining_from_inflight_working(state_dir: Path) -> dict[str, Any] | None:
    """Remaining from this cycle's working.json. Never last-pass."""
    try:
        dirs = [path for path in state_dir.glob("factory-pass-*") if path.is_dir()]
    except OSError:
        return None
    dirs.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    for path in dirs:
        remaining = remaining_from_pass_dir(path)
        if remaining is not None:
            return remaining
    return None


def _state_path_for(pass_dir: str, state_path: str | None) -> Path:
    if state_path:
        return Path(state_path)
    try:
        begin = json.loads((Path(pass_dir) / "begin.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        begin = {}
    configured = str((begin or {}).get("state_path") or "")
    if configured:
        return Path(configured)
    return Path(pass_dir).expanduser().resolve().parent / "state.jsonl"


def record(*, pass_dir: str, state_path: str | None = None) -> dict[str, Any]:
    remaining = remaining_from_pass_dir(pass_dir)
    if remaining is None:
        return {"ok": True, "written": False, "pass_dir": pass_dir}
    target = _state_path_for(pass_dir, state_path)
    existing = read_pass_receipt(state_path=target)
    receipt = dict(existing) if isinstance(existing, dict) else {"kind": "pass_receipt"}
    receipt.pop("remaining", None)
    receipt["kind"] = receipt.get("kind") or "pass_receipt"
    receipt["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt["remaining"] = remaining
    receipt["remaining_source"] = "inflight_working"
    receipt["by_repo"] = list(remaining.get("by_repo") or [])
    written = write_pass_receipt(receipt, state_path=target)
    return {
        "ok": True,
        "written": True,
        "pass_dir": pass_dir,
        "path": str(written),
        "remaining": remaining,
        "remaining_source": "inflight_working",
    }


def run(*, pass_dir: str, state_path: str | None = None) -> dict[str, Any]:
    return record(pass_dir=pass_dir, state_path=state_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-record-inflight-remaining")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    parser.add_argument("--state-path", default="")
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    try:
        payload = record(
            pass_dir=str(args.pass_dir),
            state_path=str(args.state_path or "") or None,
        )
    except OSError as exc:
        return emit_exit(err(str(exc), reason="inflight_remaining"))
    return emit_exit(ok(**payload))


if __name__ == "__main__":
    raise SystemExit(main())
