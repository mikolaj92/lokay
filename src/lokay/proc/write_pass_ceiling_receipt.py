"""Write a classified pass-ceiling receipt next to the configured state file."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.config import load_config
from lokay.pass_receipt import read_pass_receipt
from lokay.proc.classify_leftover_remaining import remaining_from_receipt, remaining_has_inbox
from lokay.proc.classify_pass_ceiling import classify
from lokay.proc.merge_leftover_remaining import merge_remaining
from lokay.proc.record_inflight_remaining import remaining_from_inflight_working

_KEEP_HEALTH = frozenset({"idle", "progress"})


def _parse_receipt_ts(raw: Any) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fresh_completed_receipt(
    receipt_path: Path, *, ceiling_seconds: float, now: float | None = None
) -> dict[str, Any] | None:
    """Return a this-tick idle/progress receipt that the slot watchdog must keep."""
    existing = read_pass_receipt(path=receipt_path)
    if not existing:
        return None
    if str(existing.get("health") or "") not in _KEEP_HEALTH:
        return None
    stamped = _parse_receipt_ts(existing.get("ts"))
    if stamped is None:
        return None
    age = (time.time() if now is None else now) - stamped
    if age < 0.0 or age > float(ceiling_seconds):
        return None
    return existing


def write(config_path: str, ceiling_seconds: float) -> dict:
    try:
        receipt = load_config(config_path).state_path.parent / "last-pass.json"
    except (OSError, ValueError, FileNotFoundError):
        receipt = Path.home() / ".lokay" / "last-pass.json"
    kept = fresh_completed_receipt(receipt, ceiling_seconds=float(ceiling_seconds))
    if kept is not None:
        return kept
    last_pass = remaining_from_receipt(read_pass_receipt(path=receipt))
    since = time.time() - max(0.0, float(ceiling_seconds)) - 2.0
    inflight = remaining_from_inflight_working(receipt.parent, since=since)
    if inflight is not None:
        remaining, remaining_source = merge_remaining(last_pass, inflight), "inflight_working"
    elif last_pass and remaining_has_inbox(last_pass):
        remaining, remaining_source = last_pass, None
    else:
        remaining, remaining_source = None, None
    payload = classify(
        state_dir=receipt.parent,
        elapsed_seconds=float(ceiling_seconds),
        remaining=remaining,
        remaining_source=remaining_source,
    )
    payload["pass_ceiling_seconds"] = float(ceiling_seconds)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tmp = receipt.with_name(f".{receipt.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        tmp.replace(receipt)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return payload


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    payload = write(args[0], float(args[1]))
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
