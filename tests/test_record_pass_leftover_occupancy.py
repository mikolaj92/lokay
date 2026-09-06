"""#1017: leftover ready must not include repos with live issue_to_pr."""

from lokay.proc.record_pass import _issues_leftover_remaining, run_record_pass


def test_leftover_drops_occupied_repo_rows():
    remaining = _issues_leftover_remaining(
        {
            "result": {
                "leftover": 3,
                "leftover_issues": [
                    {"repo": "mikolaj92/Temida", "issue": 5191},
                    {"repo": "mikolaj92/Fala", "issue": 186},
                    {"repo": "mikolaj92/Temida", "issue": 5190},
                ],
            }
        },
        {"inbox": 2},
        working={"occupied_repos": ["mikolaj92/Temida"]},
    )
    assert remaining["leftover"] == 1
    assert remaining["leftover_issues"] == [{"repo": "mikolaj92/Fala", "issue": 186}]


def test_started_launch_repo_is_not_leftover_ready():
    remaining = _issues_leftover_remaining(
        {
            "result": {
                "launched": "started",
                "repo": "mikolaj92/Temida",
                "issue": 5191,
                "leftover_issues": [
                    {"repo": "mikolaj92/Temida", "issue": 5190},
                    {"repo": "mikolaj92/Fala", "issue": 186},
                ],
            }
        },
        {},
        working={},
    )
    assert remaining["leftover"] == 1
    assert remaining["leftover_issues"][0]["repo"] == "mikolaj92/Fala"


def test_record_pass_paragon_matches_occupancy(tmp_path):
    pass_dir = tmp_path / "factory-pass-1"
    pass_dir.mkdir()
    (pass_dir / "begin.json").write_text("{\"state_path\": \"" + str(tmp_path / "state.jsonl") + "\"}")
    (pass_dir / "tick.json").write_text("{\"remaining\": {\"inbox\": 1}, \"health\": \"idle\"}")
    (pass_dir / "working.json").write_text(
        "{\"occupied_repos\": [\"mikolaj92/Temida\"], \"issue_to_pr_started\": 1}"
    )
    out = run_record_pass(
        pass_dir=str(pass_dir),
        issues={
            "result": {
                "leftover": 2,
                "leftover_issues": [
                    {"repo": "mikolaj92/Temida", "issue": 1},
                    {"repo": "mikolaj92/Fala", "issue": 2},
                ],
            }
        },
    )
    rem = out["result"]["remaining"]
    assert rem["leftover"] == 1
    assert rem["leftover_issues"] == [{"repo": "mikolaj92/Fala", "issue": 2}]
