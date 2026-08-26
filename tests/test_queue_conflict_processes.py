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


def _live_shape_pass(tmp_path):
    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.begin_path(path),
        {
            "repos": ["mikolaj92/Temida", "mikolaj92/reviewkit", "mikolaj92/lokay"],
            "live": True,
            "issue_budget": 1,
            "executor_enabled": True,
            "incident_repo": "mikolaj92/lokay",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "progress": 0,
            "remaining_ready": 2,
            "ready_by_repo": {
                "mikolaj92/Temida": [
                    {
                        "number": 4990,
                        "title": "direction, not implement",
                        "labels": ["work:ready"],
                    }
                ],
                "mikolaj92/reviewkit": [
                    {
                        "number": 205,
                        "title": "catalog hole",
                        "labels": ["work:ready"],
                    }
                ],
            },
            "inbox_issues_by_repo": {
                "mikolaj92/Temida": [
                    {
                        "number": 4990,
                        "title": "direction, not implement",
                        "labels": ["work:ready"],
                    }
                ],
                "mikolaj92/reviewkit": [
                    {
                        "number": 205,
                        "title": "catalog hole",
                        "labels": ["work:ready"],
                    }
                ],
            },
            "prs_by_repo": {},
            "pr_survey_failed": [],
            "occupied_repos": [],
        },
    )
    return path


def test_needs_human_on_first_product_selects_next_catalog_row(tmp_path):
    from lokay.proc.advance_implementation_selection import run as advance
    from lokay.proc.implementation_selection_catalog import run as catalog
    from lokay.proc.persist_implementation_selection import persist
    from lokay.proc.prepare_implementation_selection import prepare
    from lokay.proc.record_queue_conflict import record
    from lokay.proc.select_queue_conflict_candidate import select

    path = _live_shape_pass(tmp_path)
    persist(
        pass_dir=str(path),
        reduced=catalog(
            prepare(pass_dir=str(path), slot_count=30), pass_dir=str(path)
        ),
    )
    first = select(pass_dir=str(path))
    assert first["repo"] == "mikolaj92/Temida" and first["issue"] == 4990
    assert pass_io.read_json(pass_io.implement_path(path))["clean_repos"] == [
        "mikolaj92/Temida"
    ]
    recorded = record(
        pass_dir=str(path),
        outcome={
            "route": "needs_human",
            "repo": "mikolaj92/Temida",
            "issue": 4990,
            "decision": {
                "reason": "execution_scope_ambiguous",
                "detail": {"note": "implement_here_or_create_separate_issue"},
            },
        },
        remove={},
        tracker={},
    )
    assert recorded["route"] == "needs_human"
    nxt = advance(pass_dir=str(path), recorded=recorded)
    assert nxt["ok"] is True and nxt["advanced"] is True
    assert nxt["clean_repos"] == ["mikolaj92/reviewkit"]
    assert nxt["repo"] == "mikolaj92/reviewkit" and nxt["issue"] == 205
    assert nxt["candidate"]["number"] == 205
    implement = pass_io.read_json(pass_io.implement_path(path))
    assert implement["clean_repos"] == ["mikolaj92/reviewkit"]
    assert select(pass_dir=str(path))["issue"] == 205


def test_needs_human_does_not_reselect_parked_inbox_issue(tmp_path):
    from lokay.proc.advance_implementation_selection import run as advance
    from lokay.proc.record_queue_conflict import record

    path = _live_shape_pass(tmp_path)
    pass_io.write_json(
        pass_io.implement_path(path),
        {"clean_repos": ["mikolaj92/Temida"], "issue_budget": 1, "lane": "product"},
    )
    recorded = record(
        pass_dir=str(path),
        outcome={
            "route": "needs_human",
            "repo": "mikolaj92/Temida",
            "issue": 4990,
            "decision": {"reason": "execution_scope_ambiguous"},
        },
        remove={},
        tracker={},
    )
    working = pass_io.read_json(pass_io.working_path(path))
    assert working["ready_by_repo"]["mikolaj92/Temida"] == []
    assert working["inbox_issues_by_repo"]["mikolaj92/Temida"] == []
    nxt = advance(pass_dir=str(path), recorded=recorded)
    assert nxt["clean_repos"] == ["mikolaj92/reviewkit"]
    assert nxt["issue"] == 205
