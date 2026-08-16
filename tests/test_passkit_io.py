"""factory-pass workspace hygiene."""

from __future__ import annotations

import os
import time
from pathlib import Path

from lokay.passkit import io as pass_io


def test_prune_keeps_newest_and_current(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    made: list[Path] = []
    now = time.time()
    for i in range(12):
        d = tmp_path / f"factory-pass-{i:04d}-deadbeef"
        d.mkdir()
        (d / "begin.json").write_text("{}", encoding="utf-8")
        stamp = now - (12 - i)
        os.utime(d, (stamp, stamp))
        made.append(d)
    current = pass_io.make_pass_dir(state)
    removed = pass_io.prune_pass_dirs(state, keep=4, keep_path=current)
    leftover = sorted(p.name for p in tmp_path.glob("factory-pass-*") if p.is_dir())
    assert current.name in leftover
    assert len(leftover) <= 5  # keep 4 + current if current is extra
    assert removed >= 7
    assert made[0].name not in leftover


def test_prune_missing_root_is_zero(tmp_path: Path):
    missing = tmp_path / "nope" / "state.jsonl"
    assert pass_io.prune_pass_dirs(missing) == 0
