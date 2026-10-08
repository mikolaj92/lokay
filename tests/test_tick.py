from lokay.plan import plan


def test_skip_is_not_a_candidate():
    snapshot = {"repos": {"o/r": {"issues": [
        {"number": 1, "owner_commands": ["/lokay build"]},
        {"number": 2, "owner_commands": ["/lokay skip"]},
    ]}}}
    out = plan(snapshot)
    assert [item["work_id"] for item in out["candidates"]] == ["o/r#1"]
    assert out["free_slots"] == 1
