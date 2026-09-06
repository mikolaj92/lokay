"""#1067: occupancy / idle wipe must not erase non-occupied leftover fuel."""

from __future__ import annotations

from pathlib import Path

from lokay.pass_receipt import write_pass_receipt
from lokay.passkit import io as pass_io
from lokay.proc.record_pass import _issues_leftover_remaining, run_record_pass
from lokay.proc.survey_ttl import last_pass_is_empty_idle


def test_occupancy_without_relist_keeps_prior_leftover_issues():
    remaining = _issues_leftover_remaining(
        {
            "result": {
                "route": "none",
                "reason": "occupied",
                "leftover": 0,
                "leftover_issues": [],
            }
        },
        {
            "leftover": 2,
            "leftover_issues": [
                {"repo": "mikolaj92/Docxtor", "issue": 160},
                {"repo": "mikolaj92/Fala", "issue": 223},
            ],
        },
        working={"occupied_repos": ["mikolaj92/Fala"]},
    )
    assert remaining["leftover"] == 1
    assert remaining["leftover_issues"] == [{"repo": "mikolaj92/Docxtor", "issue": 160}]


def test_occupancy_without_leftover_key_keeps_prior():
    remaining = _issues_leftover_remaining(
        {"result": {"route": "skip", "reason": "host_updated"}},
        {
            "leftover": 1,
            "leftover_issues": [{"repo": "mikolaj92/Docxtor", "issue": 160}],
        },
        working={"live_issue_to_pr_repos": ["mikolaj92/Fala"]},
    )
    assert remaining["leftover"] == 1
    assert remaining["leftover_issues"][0]["issue"] == 160


def test_fresh_list_all_occupied_still_zeros_ready_leftover():
    remaining = _issues_leftover_remaining(
        {
            "result": {
                "leftover": 1,
                "leftover_issues": [{"repo": "mikolaj92/Fala", "issue": 223}],
            }
        },
        {"leftover": 9, "leftover_issues": [{"repo": "mikolaj92/Docxtor", "issue": 160}]},
        working={"occupied_repos": ["mikolaj92/Fala"]},
    )
    assert remaining["leftover"] == 0
    assert "leftover_issues" not in remaining


def test_record_pass_seeds_from_last_pass_under_occupancy(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    write_pass_receipt(
        {
            "kind": "pass_receipt",
            "remaining": {
                "leftover": 2,
                "leftover_issues": [
                    {"repo": "mikolaj92/Docxtor", "issue": 160},
                    {"repo": "mikolaj92/Fala", "issue": 223},
                ],
            },
        },
        state_path=state,
    )
    pass_dir = tmp_path / "factory-pass-1"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"state_path": str(state), "live": True, "config_path": "x"},
    )
    # compute_health-shaped tick: no leftover keys
    pass_io.write_json(
        pass_io.tick_path(pass_dir),
        {"remaining": {"inbox": 0, "ready": 0}, "health": "idle", "idle": True},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"occupied_repos": ["mikolaj92/Fala"], "issue_to_pr_started": 1},
    )
    out = run_record_pass(
        pass_dir=str(pass_dir),
        issues={
            "result": {
                "route": "idle",
                "leftover": 0,
                "leftover_issues": [],
            }
        },
    )
    rem = out["result"]["remaining"]
    assert rem["leftover"] == 1
    assert rem["leftover_issues"] == [{"repo": "mikolaj92/Docxtor", "issue": 160}]
    assert rem.get("issue_to_pr_started") == 1
    assert out["result"]["idle"] is False
    from lokay.pass_receipt import read_pass_receipt

    receipt = read_pass_receipt(state_path=state)
    assert receipt is not None
    assert receipt["remaining"]["leftover"] == 1
    assert receipt["remaining"]["leftover_issues"][0]["repo"] == "mikolaj92/Docxtor"


def test_last_pass_with_leftover_is_not_empty_idle():
    assert (
        last_pass_is_empty_idle(
            {
                "health": "idle",
                "idle": True,
                "remaining": {"leftover": 31, "leftover_issues": [{"repo": "a/b", "issue": 1}]},
            }
        )
        is False
    )
    assert (
        last_pass_is_empty_idle(
            {"health": "idle", "idle": True, "remaining": {"leftover": 0, "inbox": 0, "ready": 0}}
        )
        is True
    )
