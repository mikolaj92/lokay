"""Contracts for minimal self-repair preparation validators."""


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
