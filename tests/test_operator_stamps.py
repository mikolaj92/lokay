"""Shared operator-stamp helpers: one body for six domains."""

import time
from pathlib import Path

from lokay.operator_stamps import (
    clear_stamp,
    is_operator_stamp,
    lokay_home_stamp_path,
    touch_stamp,
)


def test_touch_stamp_writes_epoch_and_creates_parents(tmp_path: Path) -> None:
    stamp = tmp_path / "deep" / "nest" / "x.stamp"
    before = int(time.time())
    touch_stamp(stamp)
    assert stamp.parent.is_dir()
    assert int(stamp.read_text(encoding="utf-8")) >= before


def test_touch_and_clear_stamp_tolerate_none_and_missing(tmp_path: Path) -> None:
    touch_stamp(None)
    clear_stamp(None)
    clear_stamp(tmp_path / "missing.stamp")  # no raise


def test_operator_stamp_path_lives_under_home_lokay() -> None:
    path = lokay_home_stamp_path("inc.stamp")
    assert path == Path.home() / ".lokay" / "inc.stamp"


def test_is_operator_stamp_matches_by_resolve(tmp_path: Path) -> None:
    name = "probe.stamp"
    assert is_operator_stamp(Path.home() / ".lokay" / name, name)
    assert not is_operator_stamp(tmp_path / name, name)
