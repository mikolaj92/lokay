"""Contracts for minimal self-repair preparation validators."""

import json


def _changes(**kw):
    row = {
        "route": "changes",
        "uncommitted": "empty",
        "ahead": 0,
        "fingerprint": "deadbeef",
        "head": "a" * 40,
    }
    row.update(kw)
    return row


def test_plan_only_uncommitted_is_preserved():
    from lokay.proc.validate_self_repair_change_shape import validate

    assert (
        "uncommitted plan evidence"
        in validate(_changes(uncommitted="plan_only"))["error"]
    )


def test_dirty_with_commits_is_preserved():
    from lokay.proc.validate_self_repair_change_shape import validate

    assert (
        "unrecognized commits"
        in validate(_changes(uncommitted="real", ahead=1))["error"]
    )


def test_empty_worktree_routes_remove():
    from lokay.proc.validate_self_repair_change_shape import validate

    assert validate(_changes())["route"] == "remove"


def test_dirty_worktree_routes_ancestry():
    from lokay.proc.validate_self_repair_change_shape import validate

    assert validate(_changes(uncommitted="real"))["route"] == "ancestry"


def test_exact_commit_is_valid():
    from lokay.proc.validate_self_repair_commit import validate

    row = {
        **_changes(ahead=1),
        "route": "commit",
        "subject": "self-repair: deadbeef",
        "committed": "real",
    }
    assert validate(row)["route"] == "ancestry"


def test_unrecognized_commit_is_preserved():
    from lokay.proc.validate_self_repair_commit import validate

    row = {
        **_changes(ahead=1),
        "route": "commit",
        "subject": "other",
        "committed": "real",
    }
    assert "unrecognized committed" in validate(row)["error"]


def test_committed_plan_only_is_preserved():
    from lokay.proc.validate_self_repair_commit import validate

    row = {
        **_changes(ahead=1),
        "route": "commit",
        "subject": "self-repair: deadbeef",
        "committed": "plan_only",
    }
    assert "committed plan evidence" in validate(row)["error"]


def test_published_result_has_no_worktree():
    from lokay.proc.select_self_repair_prepare_result import select

    out = select(
        {"repo": "mikolaj92/lokay", "worktree": "/tmp/w"},
        {"route": "live"},
        {"route": "published", "commit": "b" * 40},
        {},
        {},
        {},
        {},
    )
    assert out["already_on_main"] and out["worktree"] == ""


def test_planned_result_does_not_mutate():
    from lokay.proc.select_self_repair_prepare_result import select

    assert (
        select({"worktree": "/tmp/w"}, {"route": "planned"}, {}, {}, {}, {}, {})[
            "planned"
        ]
        is True
    )


def test_timed_out_committed_candidate_is_removed(tmp_path):
    import sqlite3

    from lokay.proc.inspect_self_repair_ancestry import inspect

    head = "c" * 40
    journal = tmp_path / "self_repair_validate"
    journal.mkdir()
    db = journal / "state.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE processes ("
            "id TEXT, output_json TEXT, started_at TEXT)"
        )
        conn.execute(
            "INSERT INTO processes VALUES (?, ?, ?)",
            (
                "self_repair_validate:run_self_repair_tests",
                '{"values": {"head": "%s", "test_timed_out": true, "ok": false}}'
                % head,
                "2026-09-06T00:00:00Z",
            ),
        )
    out = inspect(
        {
            "worktree": str(tmp_path / "w"),
            "base_sha": "b" * 40,
            "ahead": 1,
            "head": head,
            "uncommitted": "empty",
            "journal_home": str(tmp_path),
        }
    )
    assert out["route"] == "remove"
    assert "timed out" in out["error"]


def test_redacted_timeout_error_is_removed(tmp_path):
    import sqlite3

    from lokay.proc.inspect_self_repair_ancestry import inspect

    head = "e97696d891e6e8d34cccf6ff357b488e6d5e67ad"
    journal = tmp_path / "self_repair_validate"
    journal.mkdir()
    with sqlite3.connect(journal / "state.sqlite") as conn:
        conn.execute(
            "CREATE TABLE processes ("
            "id TEXT, input_json TEXT, output_json TEXT, error_json TEXT, started_at TEXT)"
        )
        conn.execute(
            "INSERT INTO processes VALUES (?, ?, ?, ?, ?)",
            (
                "self_repair_validate:run_self_repair_tests",
                json.dumps({"expected_commit": head, "worktree": "/tmp/w"}),
                "{}",
                json.dumps(
                    {
                        "code": "adapter_failed",
                        "message": (
                            'subprocess adapter failed: {"expected_commit": '
                            '"e97696d89<redacted>e6e8d34cccf6ff357b488e6d5e67ad", '
                            '"test_timed_out": true, "route": "failed"}'
                        ),
                    }
                ),
                "2026-09-05T23:55:43Z",
            ),
        )
    out = inspect(
        {
            "worktree": str(tmp_path / "w"),
            "base_sha": "b" * 40,
            "ahead": 1,
            "head": head,
            "uncommitted": "empty",
            "journal_home": str(tmp_path),
        }
    )
    assert out["route"] == "remove"
