"""Slot watchdog must not erase a this-tick idle/progress receipt."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lokay.proc.write_pass_ceiling_receipt import fresh_completed_receipt, write


def _cfg(tmp_path: Path) -> str:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  command: true
  args: ["{{prompt}}"]
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return str(cfg)


def _write_receipt(tmp_path: Path, *, health: str, age_seconds: float) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    payload = {
        "kind": "pass_receipt",
        "health": health,
        "ok": True,
        "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining": {"inbox": 0, "ready": 0},
    }
    (tmp_path / "last-pass.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return payload


def test_fresh_idle_receipt_is_kept(tmp_path: Path):
    payload = _write_receipt(tmp_path, health="idle", age_seconds=40)
    kept = fresh_completed_receipt(
        tmp_path / "last-pass.json", ceiling_seconds=180.0, now=time.time()
    )
    assert kept is not None
    assert kept["health"] == "idle"
    assert kept["ts"] == payload["ts"]


def test_fresh_progress_receipt_is_kept(tmp_path: Path):
    _write_receipt(tmp_path, health="progress", age_seconds=10)
    kept = fresh_completed_receipt(
        tmp_path / "last-pass.json", ceiling_seconds=180.0, now=time.time()
    )
    assert kept is not None
    assert kept["health"] == "progress"


def test_stale_idle_receipt_is_not_kept(tmp_path: Path):
    _write_receipt(tmp_path, health="idle", age_seconds=240)
    kept = fresh_completed_receipt(
        tmp_path / "last-pass.json", ceiling_seconds=180.0, now=time.time()
    )
    assert kept is None


def test_write_keeps_this_tick_idle_over_ceiling(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "state.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "activity.json").write_text(
        json.dumps({"transitions": 108, "path": "factory_pass", "atom": "summarize_daemon_cycle"}),
        encoding="utf-8",
    )
    # Empty this-tick pass dir would otherwise look like inflight_working.
    live = tmp_path / "factory-pass-1-deadbeef"
    live.mkdir()
    (live / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 0,
                "remaining_ready": 0,
                "remaining_prs": 0,
                "survey_errors": 0,
                "inbox_issues_by_repo": {},
                "ready_by_repo": {},
                "inbox_by_repo": {},
            }
        ),
        encoding="utf-8",
    )
    idle = _write_receipt(tmp_path, health="idle", age_seconds=40)
    out = write(cfg, 180.0)
    assert out["health"] == "idle"
    assert out["ts"] == idle["ts"]
    on_disk = json.loads((tmp_path / "last-pass.json").read_text(encoding="utf-8"))
    assert on_disk["health"] == "idle"
    assert on_disk["ts"] == idle["ts"]


def test_write_replaces_stale_idle_with_ceiling(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "state.jsonl").write_text("", encoding="utf-8")
    _write_receipt(tmp_path, health="idle", age_seconds=240)
    out = write(cfg, 180.0)
    assert out["health"] == "pass_ceiling"
    on_disk = json.loads((tmp_path / "last-pass.json").read_text(encoding="utf-8"))
    assert on_disk["health"] == "pass_ceiling"
