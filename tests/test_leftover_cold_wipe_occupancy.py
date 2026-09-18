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


def test_fresh_list_all_occupied_keeps_prior_other_repos():
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
    assert remaining["leftover"] == 1
    assert remaining["leftover_issues"] == [{"repo": "mikolaj92/Docxtor", "issue": 160}]


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
    assert (
        last_pass_is_empty_idle(
            {
                "health": "idle",
                "idle": True,
                "remaining": {
                    "leftover": 0,
                    "leftover_prs": [
                        {"repo": "mikolaj92/VibeFront", "pr": 30, "head_sha": "abc"}
                    ],
                },
            }
        )
        is False
    )

def test_consumed_pr_sieve_leftover_is_not_reseeded():
    from lokay.proc.record_pass import _prs_leftover_remaining

    remaining = _prs_leftover_remaining(
        {
            "result": {
                "pr": 39,
                "repo": "mikolaj92/OpenAPITransportKit",
                "head_sha": "f654e881",
                "route": "fail_closed",
                "reason": "ocr_contract_rejected",
                "leftover": 2,
                "leftover_prs": [
                    {
                        "repo": "mikolaj92/VibeFront",
                        "pr": 30,
                        "head_sha": "abc111",
                        "branch": "ai/fix/30-x",
                    },
                    {
                        "repo": "mikolaj92/splot",
                        "pr": 55,
                        "head_sha": "def222",
                        "branch": "ai/fix/55-x",
                    },
                ],
                "skipped_pr": 39,
                "skipped_repo": "mikolaj92/OpenAPITransportKit",
                "skipped_head_sha": "f654e881",
            }
        },
        {
            "leftover_prs": [
                {
                    "repo": "mikolaj92/OpenAPITransportKit",
                    "pr": 39,
                    "head_sha": "f654e881",
                    "branch": "ai/fix/39-x",
                }
            ]
        },
    )
    assert remaining["leftover_prs"][0]["pr"] == 30
    assert remaining["skipped_pr"] == 39
    assert remaining["skipped_head_sha"] == "f654e881"
    assert all(row["pr"] != 39 for row in remaining["leftover_prs"])


def test_record_pass_keeps_consumed_pr_leftover(tmp_path: Path):
    pass_dir = tmp_path / "factory-pass-pr"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"state_path": str(tmp_path / "state.jsonl"), "live": True, "config_path": "x"},
    )
    leftover_prs = [
        {
            "repo": "mikolaj92/VibeFront",
            "pr": 30,
            "head_sha": "abc111",
            "branch": "ai/fix/30-x",
        }
    ]
    out = run_record_pass(
        pass_dir=str(pass_dir),
        prs={
            "result": {
                "route": "fail_closed",
                "reason": "ocr_contract_rejected",
                "repo": "mikolaj92/OpenAPITransportKit",
                "pr": 39,
                "head_sha": "f654e881",
                "leftover": 1,
                "leftover_prs": leftover_prs,
                "skipped_pr": 39,
                "skipped_repo": "mikolaj92/OpenAPITransportKit",
                "skipped_head_sha": "f654e881",
            }
        },
    )
    rem = out["result"]["remaining"]
    assert rem["leftover_prs"] == leftover_prs
    assert rem["skipped_pr"] == 39
    assert rem["skipped_head_sha"] == "f654e881"
    from lokay.pass_receipt import read_pass_receipt

    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    assert receipt["remaining"]["leftover_prs"] == leftover_prs


def test_exhausted_pr_leftover_keeps_skipped_identity():
    from lokay.proc.record_pass import _prs_leftover_remaining

    remaining = _prs_leftover_remaining(
        {
            "result": {
                "route": "none",
                "reason": "no_open_pr",
                "leftover": 0,
                "leftover_prs": [],
            }
        },
        {
            "leftover_prs": [],
            "skipped_pr": 39,
            "skipped_repo": "mikolaj92/OpenAPITransportKit",
            "skipped_head_sha": "f654e881",
        },
    )
    assert remaining["leftover_prs"] == []
    assert remaining["skipped_pr"] == 39
    assert remaining["skipped_head_sha"] == "f654e881"


def test_missing_pr_leftover_keeps_prior():
    from lokay.proc.record_pass import _prs_leftover_remaining

    prior = [
        {
            "repo": "mikolaj92/VibeFront",
            "pr": 30,
            "head_sha": "abc111",
            "branch": "ai/fix/30-x",
        }
    ]
    remaining = _prs_leftover_remaining(
        {"result": {"route": "none", "reason": "no_open_pr"}},
        {"leftover_prs": prior},
    )
    assert remaining["leftover_prs"] == prior


def test_consumed_host_ops_leftover_is_not_reseeded():
    remaining = _issues_leftover_remaining(
        {
            "result": {
                "issue": 48,
                "repo": "mikolaj92/dotfiles",
                "route": "skip",
                "reason": "host_ops",
                "leftover": 0,
                "leftover_issues": [],
                "launched": None,
            }
        },
        {
            "leftover": 2,
            "leftover_issues": [
                {"repo": "mikolaj92/dotfiles", "issue": 47},
                {"repo": "mikolaj92/dotfiles", "issue": 48},
            ],
            "skipped_issue": 48,
            "skipped_repo": "mikolaj92/dotfiles",
        },
        working={"occupied_repos": []},
    )
    assert remaining["leftover"] == 0
    assert "leftover_issues" not in remaining


def test_tick_leftover_zero_still_reseeds_leftover_issues(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    write_pass_receipt(
        {
            "kind": "pass_receipt",
            "remaining": {
                "leftover": 2,
                "leftover_issues": [
                    {"repo": "mikolaj92/takt", "issue": 43},
                    {"repo": "mikolaj92/takt", "issue": 44},
                ],
            },
        },
        state_path=state,
    )
    pass_dir = tmp_path / "factory-pass-2"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"state_path": str(state), "live": True, "config_path": "x"},
    )
    # Stale tick leftover:0 without leftover_issues must not block reseed (#1071).
    pass_io.write_json(
        pass_io.tick_path(pass_dir),
        {"remaining": {"leftover": 0}, "health": "hosted", "idle": False},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"occupied_repos": ["mikolaj92/my-usermanager"]},
    )
    out = run_record_pass(
        pass_dir=str(pass_dir),
        issues={"result": {"route": "idle", "leftover": 0, "leftover_issues": []}},
    )
    rem = out["result"]["remaining"]
    assert rem["leftover"] == 2
    assert rem["leftover_issues"][0]["issue"] == 43


def test_select_executor_result_cap_keeps_prepared_leftover():
    from lokay.proc.select_executor_result import select

    out = select(
        {
            "last": {},
            "spent": 1,
            "cap": 1,
            "budget": 0,
            "leftover": 2,
            "leftover_issues": [
                {"repo": "mikolaj92/takt", "issue": 43},
                {"repo": "mikolaj92/takt", "issue": 44},
            ],
        },
        rows=[{"ok": True, "route": "empty", "slot": 1}],
    )
    assert out["route"] == "cap"
    assert out["result"]["leftover"] == 2
    assert out["result"]["leftover_issues"][0]["issue"] == 43


def test_select_executor_result_keeps_explicit_empty_leftover_issues():
    from lokay.proc.select_executor_result import select

    out = select(
        {
            "last": {
                "issue": 48,
                "repo": "mikolaj92/dotfiles",
                "route": "skip",
                "reason": "host_ops",
                "leftover": 0,
                "leftover_issues": [],
                "launched": None,
            },
            "spent": 0,
            "cap": 1,
            "budget": 1,
        },
        rows=[],
    )
    assert out["result"]["leftover"] == 0
    assert "leftover_issues" in out["result"]
    assert out["result"]["leftover_issues"] == []


def test_select_executor_result_omits_empty_leftover_when_never_listed():
    from lokay.proc.select_executor_result import select

    out = select({"last": {}, "spent": 0, "cap": 1, "budget": 1}, rows=[])
    assert "leftover_issues" not in out["result"]
    assert out["result"]["leftover"] == 0


def test_executor_nest_empty_leftover_does_not_reseed_host_ops():
    remaining = _issues_leftover_remaining(
        {
            "ok": True,
            "route": "idle",
            "department": "executor",
            "result": {
                "issue": 48,
                "repo": "mikolaj92/dotfiles",
                "route": "skip",
                "reason": "host_ops",
                "leftover": 0,
                "leftover_issues": [],
                "launched": None,
            },
        },
        {
            "leftover": 2,
            "leftover_issues": [
                {"repo": "mikolaj92/dotfiles", "issue": 47},
                {"repo": "mikolaj92/dotfiles", "issue": 48},
            ],
        },
        working={"occupied_repos": []},
    )
    assert remaining["leftover"] == 0
    assert "leftover_issues" not in remaining

