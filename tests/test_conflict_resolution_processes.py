"""Contracts for minimal conflict-resolution processes."""

from lokay.passkit import io as pass_io


def workspace(tmp_path):
    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(
        pass_io.begin_path(path),
        {
            "repos": ["a/b"],
            "branch_prefix": "ai/fix/",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "progress": 0,
            "stuck": {"issues": {}},
            "prs_by_repo": {
                "a/b": [
                    {"number": 7, "head_ref": "ai/fix/7-x", "mergeable": "CONFLICTING"}
                ]
            },
            "ready_by_repo": {},
            "remaining_prs": 1,
            "remaining_ready": 0,
        },
    )
    return path


def test_selects_only_one_conflict(tmp_path):
    from lokay.proc.select_conflicting_pr import select

    path = workspace(tmp_path)
    out = select(pass_dir=str(path))
    assert out["route"] == "conflict" and out["pr"] == 7


def test_record_closed_removes_pr_and_adds_ready_issue(tmp_path):
    from lokay.proc.record_conflict_resolution import record
    from lokay.proc.reduce_conflict_resolution import reduce_state

    path = workspace(tmp_path)
    target = {
        "route": "conflict",
        "repo": "a/b",
        "pr": 7,
        "head_ref": "ai/fix/7-x",
        "mergeable": "CONFLICTING",
        "title": "issue 7",
    }
    reduced = reduce_state(
        working=pass_io.read_json(pass_io.working_path(path)),
        target=target,
        closed={"route": "closed", "close": {"ok": True, "closed": True}},
        resolved={"route": "issue", "issue": 7},
        cleared={"stuck": {"issues": {}}},
        ready={"applied": True, "ready": {"ok": True, "applied": True}},
    )
    out = record(pass_dir=str(path), reduced=reduced)
    working = pass_io.read_json(pass_io.working_path(path))
    assert out["closed"] == 1 and working["prs_by_repo"]["a/b"] == []
    assert working["ready_by_repo"]["a/b"][0]["number"] == 7


def test_record_planned_keeps_physical_state(tmp_path):
    from lokay.proc.record_conflict_resolution import record
    from lokay.proc.reduce_conflict_resolution import reduce_state

    path = workspace(tmp_path)
    target = {
        "route": "conflict",
        "repo": "a/b",
        "pr": 7,
        "head_ref": "ai/fix/7-x",
        "mergeable": "CONFLICTING",
    }
    reduced = reduce_state(
        working=pass_io.read_json(pass_io.working_path(path)),
        target=target,
        closed={"route": "planned", "close": {"ok": True, "planned": True}},
        resolved={},
        cleared={},
        ready={},
    )
    out = record(pass_dir=str(path), reduced=reduced)
    working = pass_io.read_json(pass_io.working_path(path))
    assert out["closed"] == 0 and len(working["prs_by_repo"]["a/b"]) == 1
