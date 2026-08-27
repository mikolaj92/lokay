"""leftover=0 + empty working + 180s ceiling must not drop inbox/ready."""

import json
from pathlib import Path

from lokay.proc.build_factory_working_state import build as build_working
from lokay.proc.classify_leftover_remaining import classify
from lokay.proc.merge_leftover_remaining import merge_remaining
from lokay.proc.record_inflight_remaining import remaining_from_working


def _last_pass_leftover_zero() -> dict:
    return {
        "leftover": 0,
        "leftover_issues": [],
        "inbox": 4,
        "ready": 5,
        "ready_with_open_pr": 1,
        "open_ai_prs": 2,
        "survey_errors": 0,
        "by_repo": [
            {"repo": "mikolaj92/Temida", "inbox": 3, "ready": 4},
            {"repo": "mikolaj92/Koksu", "inbox": 1, "ready": 1},
        ],
    }


def _empty_working() -> dict:
    return build_working({"stuck_path": "/tmp/stuck.json"})["working"]


def test_leftover_zero_empty_working_ceiling_keeps_inbox_ready():
    last_pass = _last_pass_leftover_zero()
    working = _empty_working()
    inflight = remaining_from_working(working)
    assert inflight["inbox"] == 0
    assert inflight["ready"] == 0
    assert inflight["by_repo"] == []
    assert classify(last_pass)["route"] == "merge"
    merged = merge_remaining(last_pass, inflight)
    assert merged["inbox"] == 4
    assert merged["ready"] == 5
    assert merged["leftover"] == 0
    assert merged["leftover_issues"] == []
    assert merged["by_repo"][0]["repo"] == "mikolaj92/Koksu"
    assert merged["by_repo"][0]["inbox"] == 1
    assert any(row["repo"] == "mikolaj92/Temida" and row["inbox"] == 3 for row in merged["by_repo"])


def test_ceiling_write_does_not_replace_last_pass_with_empty(tmp_path: Path):
    from lokay.compose.daemon_cycle import ceiling_remaining

    last_pass = _last_pass_leftover_zero()
    receipt = tmp_path / "last-pass.json"
    receipt.write_text(
        json.dumps({"kind": "pass_receipt", "remaining": last_pass}),
        encoding="utf-8",
    )
    pass_dir = tmp_path / "factory-pass-1-live"
    pass_dir.mkdir()
    (pass_dir / "working.json").write_text(
        json.dumps(_empty_working()), encoding="utf-8"
    )
    written, source = ceiling_remaining(tmp_path)
    assert written is not None
    assert source == "inflight_working"
    assert written["inbox"] == 4
    assert written["ready"] == 5
    assert written["leftover"] == 0
    assert written["by_repo"]


def test_remaining_from_working_keeps_leftover_fields():
    working = _empty_working()
    working["leftover"] = 0
    working["leftover_issues"] = []
    remaining = remaining_from_working(working)
    assert remaining["leftover"] == 0
    assert remaining["leftover_issues"] == []


def test_merge_never_replaces_nonempty_inflight_inbox_with_zeros():
    last_pass = {"leftover": 0, "inbox": 0, "ready": 0, "by_repo": []}
    inflight = {
        "inbox": 7,
        "ready": 2,
        "by_repo": [{"repo": "mikolaj92/Temida", "inbox": 7, "ready": 2}],
    }
    merged = merge_remaining(last_pass, inflight)
    assert merged["inbox"] == 7
    assert merged["ready"] == 2
    assert merged["by_repo"][0]["inbox"] == 7
