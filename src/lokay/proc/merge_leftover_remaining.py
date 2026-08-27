"""Leaf: merge last-pass leftover remaining into working; never write zeros over inbox."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.pass_receipt import read_pass_receipt
from lokay.proc._common import add_config_live, load_cfg
from lokay.proc.classify_leftover_remaining import (
    classify,
    remaining_from_receipt,
)
from lokay.proc.record_inflight_remaining import remaining_from_working


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def leftover_fields(source: dict[str, Any] | None) -> dict[str, Any]:
    """Copy leftover keys so a leftover=0 write does not drop the field."""
    if not isinstance(source, dict):
        return {}
    kept: dict[str, Any] = {}
    for key, value in source.items():
        if key == "leftover" or key.startswith("leftover_"):
            kept[key] = value
    return kept


def _row_inbox(row: Any) -> int:
    if not isinstance(row, dict):
        return 0
    return _as_int(row.get("inbox"))


def _row_ready(row: Any) -> int:
    if not isinstance(row, dict):
        return 0
    return _as_int(row.get("ready"))


def merge_by_repo(last_pass: Any, inflight: Any) -> list[dict[str, Any]]:
    """Union by_repo; never replace a non-empty inflight inbox with zeros."""
    last_rows = last_pass if isinstance(last_pass, list) else []
    inflight_rows = inflight if isinstance(inflight, list) else []
    by_name: dict[str, dict[str, Any]] = {}
    for row in last_rows:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        by_name[repo] = {
            "repo": repo,
            "inbox": _row_inbox(row),
            "ready": _row_ready(row),
        }
    for row in inflight_rows:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        current = by_name.get(repo, {"repo": repo, "inbox": 0, "ready": 0})
        inbox = _row_inbox(row)
        ready = _row_ready(row)
        if inbox > 0:
            current["inbox"] = inbox
        if ready > 0:
            current["ready"] = ready
        by_name[repo] = current
    return [by_name[name] for name in sorted(by_name)]


def merge_remaining(
    last_pass: dict[str, Any] | None,
    inflight: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge last-pass inbox/ready/by_repo into inflight remaining.

    Never replace a non-empty inflight inbox with zeros.
    """
    last = last_pass if isinstance(last_pass, dict) else {}
    current = inflight if isinstance(inflight, dict) else {}
    last_inbox = _as_int(last.get("inbox"))
    last_ready = _as_int(last.get("ready"))
    inflight_inbox = _as_int(current.get("inbox"))
    inflight_ready = _as_int(current.get("ready"))
    inbox = inflight_inbox if inflight_inbox > 0 else last_inbox
    ready = inflight_ready if inflight_ready > 0 else last_ready
    merged = dict(current)
    merged.update(leftover_fields(last))
    merged.update(leftover_fields(current))
    merged["inbox"] = inbox
    merged["ready"] = ready
    last_pr = _as_int(last.get("ready_with_open_pr"))
    inflight_pr = _as_int(current.get("ready_with_open_pr"))
    merged["ready_with_open_pr"] = inflight_pr if inflight_pr > 0 else last_pr
    last_prs = _as_int(last.get("open_ai_prs"))
    inflight_prs = _as_int(current.get("open_ai_prs"))
    merged["open_ai_prs"] = inflight_prs if inflight_prs > 0 else last_prs
    last_err = _as_int(last.get("survey_errors"))
    inflight_err = _as_int(current.get("survey_errors"))
    merged["survey_errors"] = inflight_err if inflight_err > 0 else last_err
    merged["by_repo"] = merge_by_repo(last.get("by_repo"), current.get("by_repo"))
    return merged


def apply_remaining_to_working(
    working: dict[str, Any], remaining: dict[str, Any]
) -> dict[str, Any]:
    """Stamp remaining counts onto working.json without wiping inflight lists."""
    updated = dict(working)
    updated["remaining_inbox"] = _as_int(remaining.get("inbox"))
    updated["remaining_ready"] = _as_int(remaining.get("ready"))
    updated["remaining_ready_with_pr"] = _as_int(remaining.get("ready_with_open_pr"))
    updated["remaining_prs"] = _as_int(remaining.get("open_ai_prs"))
    updated["survey_errors"] = _as_int(remaining.get("survey_errors"))
    inbox_by_repo: dict[str, int] = {}
    for row in remaining.get("by_repo") or []:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        inbox_by_repo[repo] = _row_inbox(row)
    if inbox_by_repo:
        existing = dict(updated.get("inbox_by_repo") or {})
        for repo, count in inbox_by_repo.items():
            if _as_int(existing.get(repo)) > 0 and count == 0:
                continue
            existing[repo] = count
        updated["inbox_by_repo"] = existing
    updated.update(leftover_fields(remaining))
    return updated


def merge_working(
    working: dict[str, Any] | None,
    last_pass: dict[str, Any] | None,
    *,
    route: str | None = None,
) -> dict[str, Any]:
    inflight = remaining_from_working(working if isinstance(working, dict) else {})
    decided = route or classify(last_pass).get("route")
    if decided != "merge":
        return inflight
    return merge_remaining(last_pass, inflight)


def _load_working(pass_dir: str | Path) -> dict[str, Any] | None:
    try:
        working = json.loads(
            (Path(pass_dir) / "working.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return working if isinstance(working, dict) else None


def _write_working(pass_dir: str | Path, working: dict[str, Any]) -> Path:
    path = Path(pass_dir) / "working.json"
    path.write_text(json.dumps(working, indent=2) + "\n", encoding="utf-8")
    return path


def merge(
    *,
    pass_dir: str,
    state_path: str | None = None,
) -> dict[str, Any]:
    receipt = read_pass_receipt(state_path=state_path) if state_path else read_pass_receipt()
    last_pass = remaining_from_receipt(receipt)
    decision = classify(last_pass)
    working = _load_working(pass_dir)
    if working is None:
        return {
            "ok": True,
            "written": False,
            "pass_dir": pass_dir,
            "route": decision.get("route"),
            "reason": "working_missing",
        }
    if decision.get("route") != "merge":
        return {
            "ok": True,
            "written": False,
            "pass_dir": pass_dir,
            "route": decision.get("route"),
            "reason": decision.get("reason"),
        }
    remaining = merge_working(working, last_pass, route="merge")
    updated = apply_remaining_to_working(working, remaining)
    written = _write_working(pass_dir, updated)
    return {
        "ok": True,
        "written": True,
        "pass_dir": pass_dir,
        "path": str(written),
        "route": "merge",
        "remaining": remaining,
        "reason": decision.get("reason"),
    }


def run(*, pass_dir: str, state_path: str | None = None) -> dict[str, Any]:
    return merge(pass_dir=pass_dir, state_path=state_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-merge-leftover-remaining")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    parser.add_argument("--state-path", default="")
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    cfg = load_cfg(args)
    try:
        payload = merge(
            pass_dir=str(args.pass_dir),
            state_path=str(args.state_path or "") or str(cfg.state_path or "") or None,
        )
    except OSError as exc:
        return emit_exit(err(str(exc), reason="merge_leftover_remaining"))
    return emit_exit(ok(**payload))


if __name__ == "__main__":
    raise SystemExit(main())
