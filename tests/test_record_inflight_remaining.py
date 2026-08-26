"""last-pass remaining from this cycle's working.json, not record_pass."""

import json
from pathlib import Path

from lokay.pass_receipt import read_pass_receipt
from lokay.proc.record_inflight_remaining import record, remaining_from_inflight_working


def _stale_receipt() -> dict:
    return {
        "kind": "pass_receipt",
        "ts": "2026-08-26T04:39:52Z",
        "health": "pass_ceiling",
        "remaining": {"inbox": 0, "ready": 0},
    }


def _working() -> dict:
    return {
        "remaining_inbox": 4,
        "remaining_ready": 5,
        "inbox_issues_by_repo": {
            "mikolaj92/Temida": [
                {"number": 4972, "labels": ["enhancement"]},
                {"number": 4973, "labels": ["bug"]},
                {"number": 4969, "labels": ["work:ready"]},
            ],
            "mikolaj92/Fala": [{"number": 176, "labels": ["oil"]}],
        },
        "ready_by_repo": {
            "mikolaj92/Temida": [{"number": 4968, "labels": ["ai:ready"]}],
            "mikolaj92/reviewkit": [{"number": 1}],
            "mikolaj92/app-factory": [{"number": 2}],
            "mikolaj92/lokay": [{"number": 3}],
            "mikolaj92/Fala": [{"number": 4}],
        },
    }


def test_last_pass_remaining_from_this_cycle_working_without_record_pass(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    (tmp_path / "last-pass.json").write_text(
        json.dumps(_stale_receipt()), encoding="utf-8"
    )
    pass_dir = tmp_path / "factory-pass-1-live"
    pass_dir.mkdir()
    (pass_dir / "begin.json").write_text(
        json.dumps({"state_path": str(state)}), encoding="utf-8"
    )
    (pass_dir / "working.json").write_text(json.dumps(_working()), encoding="utf-8")

    out = record(pass_dir=str(pass_dir), state_path=str(state))

    assert out["written"] is True
    assert out["remaining_source"] == "inflight_working"
    assert out["remaining"]["inbox"] == 4
    assert out["remaining"]["ready"] == 5
    persisted = read_pass_receipt(state_path=state)
    assert persisted is not None
    assert persisted["remaining"]["inbox"] == 4
    assert persisted["remaining"]["ready"] == 5
    assert persisted["remaining_source"] == "inflight_working"
    assert persisted["remaining"]["inbox"] != 0
    assert persisted["ts"] != "2026-08-26T04:39:52Z"


def test_last_pass_remaining_does_not_copy_previous_inbox_zero(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    (tmp_path / "last-pass.json").write_text(
        json.dumps(_stale_receipt()), encoding="utf-8"
    )
    pass_dir = tmp_path / "factory-pass-2-live"
    pass_dir.mkdir()
    (pass_dir / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 0,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [{"number": 4972}, {"number": 4973}]
                },
            }
        ),
        encoding="utf-8",
    )

    out = record(pass_dir=str(pass_dir), state_path=str(state))
    persisted = read_pass_receipt(state_path=state)
    assert out["remaining"]["inbox"] == 2
    assert persisted["remaining"]["inbox"] == 2
    assert persisted["remaining"] != {"inbox": 0, "ready": 0}


def test_persist_inbox_rewrites_last_pass_before_record_pass(tmp_path: Path):
    from lokay.passkit import io as pass_io
    from lokay.proc.persist_inbox_survey import persist

    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    (tmp_path / "last-pass.json").write_text(
        json.dumps(_stale_receipt()), encoding="utf-8"
    )
    pass_dir = tmp_path / "factory-pass-3-live"
    pass_dir.mkdir()
    pass_io.write_json(pass_io.begin_path(pass_dir), {"state_path": str(state)})
    pass_io.write_json(pass_io.working_path(pass_dir), {})
    persist(
        pass_dir=str(pass_dir),
        reduced={
            "state": {
                "remaining_inbox": 4,
                "survey_errors": 0,
                "inbox_survey_failed": False,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [{"number": 4972}, {"number": 4973}]
                },
                "inbox_by_repo": {"mikolaj92/Temida": 2},
                "ready_by_repo": {},
            }
        },
    )
    persisted = read_pass_receipt(state_path=state)
    assert persisted["remaining"]["inbox"] == 2
    assert persisted["remaining_source"] == "inflight_working"


def test_remaining_from_inflight_working_still_scans_newest_pass(tmp_path: Path):
    pass_dir = tmp_path / "factory-pass-9-abcd"
    pass_dir.mkdir()
    (pass_dir / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 0,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [{"number": 4972}, {"number": 4973}]
                },
            }
        ),
        encoding="utf-8",
    )
    remaining = remaining_from_inflight_working(tmp_path)
    assert remaining["inbox"] == 2
    assert remaining["by_repo"][0]["repo"] == "mikolaj92/Temida"
