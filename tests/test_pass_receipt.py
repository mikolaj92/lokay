"""Compact pass receipt for mill observability."""

from pathlib import Path

from lokay.pass_receipt import (
    build_pass_receipt,
    read_pass_receipt,
    receipt_path_for,
    write_pass_receipt,
)


def test_build_and_write_pass_receipt_roundtrip(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    tick = {
        "ok": True,
        "health": "waiting",
        "idle": False,
        "live": True,
        "progress": 0,
        "remaining": {
            "inbox": 1,
            "ready": 2,
            "actionable_open_ai_prs": 1,
            "open_ai_prs": 1,
            "max_issue_to_pr_per_pass": 3,
            "by_repo": [
                {
                    "repo": "a/b",
                    "inbox": 1,
                    "ready": 2,
                    "actionable_open_ai_prs": 1,
                    "open_ai_prs": 1,
                    "manual_open_ai_prs": 0,
                    "survey_error": False,
                }
            ],
            # bulky fields must not leak into receipt remaining
            "intake_skip_reason": None,
        },
        "note": "ci pending",
    }
    receipt = build_pass_receipt(
        tick=tick,
        merge_enabled=True,
        require_checks=True,
        require_llm_review=True,
        max_issue_to_pr_per_pass=3,
        config_path=str(tmp_path / "config.yaml"),
    )
    assert receipt["kind"] == "pass_receipt"
    assert receipt["health"] == "waiting"
    assert receipt["merge_enabled"] is True
    assert receipt["require_checks"] is True
    assert receipt["require_llm_review"] is True
    assert receipt["max_issue_to_pr_per_pass"] == 3
    assert receipt["by_repo"][0]["repo"] == "a/b"
    assert "intake_skip_reason" not in receipt["remaining"]
    assert "by_repo" in receipt["remaining"]

    path = write_pass_receipt(receipt, state_path=state)
    assert path == receipt_path_for(state)
    assert path.name == "last-pass.json"
    loaded = read_pass_receipt(state_path=state)
    assert loaded is not None
    assert loaded["health"] == "waiting"
    assert loaded["remaining"]["ready"] == 2


def test_read_pass_receipt_missing_is_none(tmp_path: Path):
    assert read_pass_receipt(path=tmp_path / "nope.json") is None
