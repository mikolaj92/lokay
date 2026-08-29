"""Task consumption contract: four operations on an in-memory source."""

from __future__ import annotations

import pytest

from lokay.tasks import MARKS, MemoryTasks, TaskId, sito_park


def _source(*rows: dict) -> MemoryTasks:
    source = MemoryTasks(plugin="memory", target="board")
    for row in rows:
        source.seed(**row)
    return source


def test_identity_is_plugin_target_number():
    identity = TaskId("memory", "board", 7)
    assert (identity.plugin, identity.target, identity.number) == ("memory", "board", 7)
    with pytest.raises(ValueError):
        TaskId("", "board", 1)
    with pytest.raises(ValueError):
        TaskId("memory", "", 1)
    with pytest.raises(ValueError):
        TaskId("memory", "board", 0)


def test_memory_source_does_four_operations():
    source = _source(
        {"number": 3, "title": "first", "assignees": ["mill"]},
        {"number": 5, "title": "second"},
    )
    listed = source.list_open()
    assert [task.number for task in listed] == [3, 5]
    assert all(task.plugin == "memory" and task.target == "board" for task in listed)

    one = source.get(listed[0].id)
    assert one is not None
    assert one.id == TaskId("memory", "board", 3)
    assert one.title == "first"

    source.comment(one.id, "working")
    ready = source.mark(one.id, "ready")
    assert ready.mark == "ready"
    assert ready.state == "OPEN"
    assert "ai:ready" in ready.labels
    assert source.get(one.id).comments == ["working"]


def test_mark_park_ready_blocked_never_closes():
    source = _source({"number": 8, "title": "open work", "labels": ["ai:ready"]})
    identity = TaskId("memory", "board", 8)
    for kind in sorted(MARKS):
        out = source.mark(identity, kind)
        assert out.mark == kind
        assert out.state == "OPEN"
        assert out.state != "CLOSED"
    assert source.get(identity).state == "OPEN"
    assert [task.number for task in source.list_open()] == [8]


def test_sito_parks_foreign_open_task_and_does_not_close():
    source = _source(
        {
            "number": 4995,
            "title": "someone else's work",
            "assignees": ["PSyron"],
            "labels": ["ai:ready"],
            "state": "OPEN",
        }
    )
    identity = TaskId("memory", "board", 4995)
    out = sito_park(source, identity, "foreign_assignee")
    assert out.state == "OPEN"
    assert out.mark == "park"
    assert "ai:blocked" in out.labels
    assert "ai:ready" not in out.labels
    assert any("Parked" in body for body in out.comments)
    assert source.get(identity).state != "CLOSED"
    assert [task.number for task in source.list_open()] == [4995]


def test_source_has_no_pr_or_repo():
    source = MemoryTasks(target="board")
    names = {name for name in dir(source) if not name.startswith("_")}
    forbidden = {
        "branch",
        "clone",
        "close",
        "git",
        "list_prs",
        "merge",
        "pr",
        "prs",
        "repo",
        "worktree",
    }
    assert names.isdisjoint(forbidden)
    assert not hasattr(source, "list_prs")
    assert not hasattr(source, "merge")
    assert not hasattr(source, "clone")
    assert not hasattr(source, "close")
    assert not hasattr(source, "repo")
    assert "repo" not in source.__dict__
    assert not hasattr(MemoryTasks, "list_prs")
    assert not hasattr(MemoryTasks, "merge")


def test_list_open_omits_closed_and_get_is_identity_bound():
    source = _source(
        {"number": 1, "title": "open"},
        {"number": 2, "title": "done", "state": "CLOSED"},
    )
    assert [task.number for task in source.list_open()] == [1]
    assert source.get(TaskId("memory", "board", 2)).state == "CLOSED"
    assert source.get(TaskId("jira", "board", 1)) is None
    assert source.get(TaskId("memory", "other", 1)) is None
    with pytest.raises(KeyError):
        source.comment(TaskId("jira", "board", 1), "no")
    with pytest.raises(ValueError):
        source.mark(TaskId("memory", "board", 1), "close")
