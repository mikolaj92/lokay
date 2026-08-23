"""Contracts for minimal queue-conflict processes."""

from lokay.passkit import io as pass_io


def test_validator_retries_then_selects_human():
    from lokay.proc.queue_conflict_boundary import select, validate

    bad = validate("not json")
    out = select(
        {"route": "candidate"},
        {"repo": "a/b", "issue": 7, "candidate": {"number": 7}},
        bad,
        bad,
    )
    assert bad["route"] == "retry"
    assert out["route"] == "needs_human"


def test_valid_agent_result_is_authoritative():
    from lokay.proc.queue_conflict_boundary import select, validate

    valid = validate(
        '{"outcome":"ready","reason":"agent_says_ready","detail":{},"summary":"ok","add_tracker":false}'
    )
    out = select(
        {"route": "candidate"},
        {"repo": "a/b", "issue": 7, "candidate": {"number": 7}},
        valid,
        {},
    )
    assert out["route"] == "ready" and out["decision"]["reason"] == "agent_says_ready"


def test_record_removes_nonready_candidate(tmp_path):
    from lokay.proc.record_queue_conflict import record

    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "progress": 0,
            "remaining_ready": 2,
            "ready_by_repo": {"a/b": [{"number": 7}, {"number": 8}]},
        },
    )
    out = record(
        pass_dir=str(path),
        outcome={
            "route": "skip",
            "repo": "a/b",
            "issue": 7,
            "decision": {"reason": "dependency"},
        },
        remove={},
        tracker={},
    )
    working = pass_io.read_json(pass_io.working_path(path))
    assert out["route"] == "skip" and working["ready_by_repo"]["a/b"] == [{"number": 8}]
    assert working["remaining_ready"] == 1
