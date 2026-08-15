"""Fail-closed harvest of finished detached issue_to_pr children into stuck.json."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lokay.child_harvest import harvest_fail_closed_children
from lokay.stuck import excluded_numbers, load_stuck, stuck_path_for


def _receipt(path: Path, *, repo: str, issue: int, pid: int) -> None:
    path.write_text(
        json.dumps({"ok": True, "detached": True, "pid": pid, "repo": repo, "issue": issue}),
        encoding="utf-8",
    )


def _event(path: Path, *, repo: str, issue: int, ok: bool, reason: str | None = None, error: str = "") -> None:
    ev: dict = {"kind": "issue_to_pr", "repo": repo, "issue": issue, "ok": ok}
    if reason is not None:
        ev["reason"] = reason
    if error:
        ev["error"] = error
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev) + "\n")


def test_dead_pid_fail_closed_reason_is_excluded(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    stuck_path = stuck_path_for(state)
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=999_999_999)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    stuck = load_stuck(stuck_path)
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    row = stuck["issues"]["a/b#7"]
    assert row.get("blocked") is True
    assert row.get("reason") == "local_repair_exhausted"


def test_live_pid_does_not_block_even_with_fail_event(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=42)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda pid: int(pid) == 42,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_dead_pid_without_event_or_reason_is_not_blocked(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    _receipt(cycle / "a__b-3.json", repo="a/b", issue=3, pid=1)
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_worktree_add_failed_error_is_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    _event(
        state,
        repo="a/b",
        issue=7,
        ok=False,
        error="worktree add failed:\nfatal: 'ai/fix/7-foo-..-bar' is not a valid branch name",
    )
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "invalid_branch_ref"


def test_waiting_reason_is_not_fail_closed(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-4.json", repo="a/b", issue=4, pid=9)
    _event(state, repo="a/b", issue=4, ok=False, reason="checks_pending")
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
    )
    assert excluded_numbers(stuck, "a/b") == set()


def test_fala_journal_fallback_when_jsonl_silent(tmp_path: Path):
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=8)
    db = tmp_path / ".lokay" / "fala" / "i2pr" / "a__b__7" / "state.sqlite"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE processes (status TEXT, output_json TEXT, error_json TEXT, updated_at TEXT)"
    )
    con.execute(
        "INSERT INTO processes VALUES (?, ?, ?, ?)",
        ("failed", "{}", '{"message":"local_repair_exhausted"}', "2026-01-01T00:00:00Z"),
    )
    con.commit()
    con.close()
    stuck = {"issues": {}}
    harvest_fail_closed_children(
        stuck,
        state_path=state,
        cycle_dir=cycle,
        is_live=lambda _pid: False,
        home=tmp_path,
    )
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "local_repair_exhausted"


def test_factory_begin_harvests_into_stuck(tmp_path: Path, monkeypatch):
    from lokay.proc.factory_begin import run_factory_begin

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    state = tmp_path / "state.jsonl"
    _receipt(cycle / "a__b-7.json", repo="a/b", issue=7, pid=999_999_999)
    _event(state, repo="a/b", issue=7, ok=False, reason="local_repair_exhausted")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
github:
  assignee: t
repos:
  - name: a/b
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
state:
  path: {state}
""",
        encoding="utf-8",
    )
    out = run_factory_begin(config_path=str(cfg), live=False)
    assert out.get("ok") is True
    stuck = load_stuck(stuck_path_for(state))
    assert 7 in excluded_numbers(stuck, "a/b")
    assert stuck["issues"]["a/b#7"].get("reason") == "local_repair_exhausted"
