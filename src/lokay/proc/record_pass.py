"""One job: write a small last-pass receipt (new_pr / merge / none)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, ok
from lokay.passkit import io as pass_io
from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import write_pass_receipt
from lokay.proc._common import add_config_live

OUTCOMES = ("merge", "new_pr", "none")
_OVERFLOW = "leftover_overflow"
_DROP = frozenset({"by_repo", "candidates", "repos", "leftover_rows"})


def _blob(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _result(value: Any) -> dict[str, Any]:
    blob = _blob(value)
    inner = blob.get("result")
    return inner if isinstance(inner, dict) else blob


def _read_optional(path: Path) -> dict[str, Any]:
    try:
        return pass_io.read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def leftover_overflowed(*blobs: Any) -> bool:
    """Leftover overflow is a skip, never a pass failure."""
    for blob in blobs:
        row = _blob(blob)
        if not row:
            continue
        if row.get("reason") == _OVERFLOW:
            return True
        if _OVERFLOW in str(row.get("error") or ""):
            return True
        if leftover_overflowed(row.get("result")):
            return True
    return False


def classify_outcome(
    *,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    working: dict[str, Any] | None = None,
    tick: dict[str, Any] | None = None,
) -> str:
    """One receipt word: merge, new_pr, or none. Merge wins (Done)."""
    prs_r = _result(prs)
    issues_r = _result(issues)
    working = _blob(working)
    tick = _blob(tick)
    rem = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    triage = _result(prs_r.get("triage") or prs_r.get("triaged"))
    merged = (
        bool(prs_r.get("merged"))
        or bool(_blob(prs).get("merged"))
        or bool(triage.get("merged"))
        or str(prs_r.get("route") or "") == "merged"
        or str(prs_r.get("triaged") or "") == "merged"
        or bool(working.get("merged_this_pass"))
    )
    if merged:
        return "merge"
    launched = str(issues_r.get("launched") or "")
    started = int(working.get("issue_to_pr_started") or rem.get("issue_to_pr_started") or 0)
    if launched in {"started", "pr", "new_pr"} or started > 0:
        return "new_pr"
    return "none"


def _state_path(begin: dict[str, Any], pass_dir: str) -> Path:
    raw = str(begin.get("state_path") or "")
    if raw:
        return Path(raw)
    if pass_dir:
        return Path(pass_dir).expanduser().resolve() / "state.jsonl"
    return Path.home() / ".lokay" / "state.jsonl"


def _small_remaining(tick: dict[str, Any], *, overflow: bool) -> dict[str, Any]:
    rem = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    if overflow:
        count = rem.get("count")
        out = {_OVERFLOW: True}
        if count is not None:
            out["count"] = count
        return out
    return {key: rem[key] for key in rem if key not in _DROP}


def run_record_pass(
    *,
    pass_dir: str = "",
    begin: dict[str, Any] | None = None,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    disk_begin = _read_optional(pass_io.begin_path(pass_dir)) if pass_dir else {}
    tick = _read_optional(pass_io.tick_path(pass_dir)) if pass_dir else {}
    working = _read_optional(pass_io.working_path(pass_dir)) if pass_dir else {}
    begin = {**disk_begin, **_blob(begin)}
    overflow = leftover_overflowed(leftover, tick, working, prs, issues, begin)
    outcome = classify_outcome(prs=prs, issues=issues, working=working, tick=tick)
    remaining = _small_remaining(tick, overflow=overflow)
    progress = int(tick.get("progress") or 0)
    if outcome != "none":
        progress = max(progress, 1)
    health = str(tick.get("health") or ("progress" if outcome != "none" else "idle"))
    if overflow and health in {"", "idle"}:
        health = "waiting"
    receipt = {
        "kind": "pass_receipt",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
        "ok": True,
        "health": health,
        "idle": bool(outcome == "none" and not overflow and tick.get("idle", outcome == "none")),
        "live": bool(begin.get("live", tick.get("live"))),
        "progress": progress,
        "lane": str(tick.get("lane") or ("product" if outcome != "none" else "idle")),
        "config": begin.get("config_path"),
        "remaining": remaining,
        _OVERFLOW: overflow,
    }
    result = {
        "ok": True,
        "health": health,
        "outcome": outcome,
        "lane": receipt["lane"],
        "progress": progress,
        "idle": receipt["idle"],
        "remaining": remaining,
        _OVERFLOW: overflow,
    }
    try:
        state_path = _state_path(begin, pass_dir)
        written = write_pass_receipt(receipt, state_path=state_path)
        append_pass_receipt(receipt, state_path=state_path)
        result["pass_receipt_path"] = str(written)
        if pass_dir:
            payload = {**tick, **result}
            pass_io.write_json(pass_io.tick_path(pass_dir), payload)
    except OSError as exc:
        result["pass_receipt_error"] = str(exc)
    return ok(pass_dir=pass_dir, outcome=outcome, tick=result, result=result)


def record(
    *,
    pass_dir: str = "",
    begin: dict[str, Any] | None = None,
    prs: dict[str, Any] | None = None,
    issues: dict[str, Any] | None = None,
    leftover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_record_pass(
        pass_dir=pass_dir,
        begin=begin,
        prs=prs,
        issues=issues,
        leftover=leftover,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-record-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    args = parser.parse_args(argv)
    return emit_exit(run_record_pass(pass_dir=str(args.pass_dir or "")))


if __name__ == "__main__":
    raise SystemExit(main())
