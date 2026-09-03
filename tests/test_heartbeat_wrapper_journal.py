"""Heartbeat wrapper journals are a pass trace, one sqlite per tick."""

from __future__ import annotations

import os
import time
from pathlib import Path

from lokay.fala_journal import wrapper_journal_dir


def test_wrapper_journal_is_fresh_and_not_the_shared_dir(tmp_path: Path):
    home = tmp_path / "home"
    shared = home / ".lokay" / "fala" / "daemon-entry"
    shared.mkdir(parents=True)
    (shared / "state.sqlite").write_bytes(b"fat")

    first = wrapper_journal_dir("daemon_entry", home=home)
    second = wrapper_journal_dir("daemon_entry", home=home)

    assert first != shared
    assert second != shared
    assert first != second
    assert first.parent == home / ".lokay" / "fala"
    assert first.name.startswith("daemon-entry-")
    assert second.name.startswith("daemon-entry-")
    assert first.is_dir() and second.is_dir()


def test_wrapper_journal_prunes_old_dirs(tmp_path: Path):
    home = tmp_path / "home"
    root = home / ".lokay" / "fala"
    root.mkdir(parents=True)
    old = []
    for i in range(4):
        path = root / f"daemon-cycle-old-{i}"
        path.mkdir()
        (path / "state.sqlite").write_bytes(b"x")
        stamp = time.time() - 1000 + i
        os.utime(path, (stamp, stamp))
        old.append(path)

    kept = wrapper_journal_dir("daemon_cycle", home=home)
    remaining = {p.name for p in root.iterdir() if p.is_dir()}
    assert kept.name in remaining
    # keep the new dir plus one previous newest leftover
    assert len(remaining) <= 3
    assert "daemon-cycle-old-0" not in remaining
    assert "daemon-cycle-old-1" not in remaining


def test_daemon_entry_and_cycle_use_wrapper_journals():
    from pathlib import Path as P

    entry = (
        P(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "daemon_entry_subflow.py"
    ).read_text(encoding="utf-8")
    cycle = (
        P(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "compose"
        / "daemon_cycle.py"
    ).read_text(encoding="utf-8")
    assert "wrapper_journal_dir" in entry
    assert 'Path.home() / ".lokay" / "fala" / "daemon-entry"' not in entry
    assert "wrapper_journal_dir" in cycle
    assert 'Path.home() / ".lokay" / "fala" / "daemon-cycle"' not in cycle
