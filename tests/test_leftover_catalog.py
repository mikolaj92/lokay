"""Leftover overflow skips the mill; it does not fail the pass."""

from lokay.proc.leftover_catalog import run
from lokay.proc.reduce_leftover_candidates import reduce_candidates


def test_too_many_repos_skip_not_fail():
    out = run(
        {"ok": True, "route": "probe", "repos": [f"o/r{i}" for i in range(40)]},
        config_path=None,
        live=False,
    )
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "leftover_overflow"
    assert out["count"] == 40


def test_too_many_candidates_skip_not_fail():
    rows = [
        {
            "candidates": [
                {"repo": f"o/r{i}", "number": i} for i in range(40)
            ]
        }
    ]
    out = reduce_candidates({"route": "probe"}, rows, slot_count=30)
    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["reason"] == "leftover_overflow"
    assert out["candidates"] == []
