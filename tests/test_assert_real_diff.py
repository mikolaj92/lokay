"""Contracts for minimal physical real-diff atoms and publication gates."""

from lokay import fala_organ
from lokay.git_real_diff import classify_changed_paths
from lokay.graph_run import describe_package


def test_diff_kind_is_mechanical():
    assert (
        classify_changed_paths([".lokay/approach.md", ".lokay/localize.json"])
        == "plan_only"
    )
    assert classify_changed_paths([]) == "empty"
    assert classify_changed_paths(["src/x.py", "uv.lock"]) == "real"


def test_ticket_scope_requires_one_named_changed_path():
    from lokay.proc.classify_ticket_scope_presence import classify

    assert (
        classify({"paths": ["src/a.py"]}, {"route": "required", "paths": ["src/a.py"]})[
            "route"
        ]
        == "continue"
    )
    assert (
        classify({"paths": ["src/b.py"]}, {"route": "required", "paths": ["src/a.py"]})[
            "reason"
        ]
        == "ticket_scope_miss"
    )


def test_ticket_scope_rejects_extra_source():
    from lokay.proc.classify_ticket_scope_extra import classify

    out = classify(
        {"paths": ["src/a.py", "src/b.py"]},
        {"route": "required", "paths": ["src/a.py"]},
        {"route": "continue"},
    )
    assert out["reason"] == "ticket_scope_extra" and out["extra_paths"] == ["src/b.py"]


def test_localize_scope_rejects_off_goal_source():
    from lokay.proc.classify_localized_diff_scope import classify

    out = classify(
        {"paths": ["src/other.py"]}, {"paths": ["src/app.py"]}, {"route": "continue"}
    )
    assert out["reason"] == "off_goal" and out["off_goal_paths"] == ["src/other.py"]


def test_progress_closes_real_plan_and_empty_routes():
    from lokay.proc.classify_real_diff_progress import classify

    assert classify({"kind": "real"}, {"route": "continue"})["route"] == "real"
    assert (
        classify({"kind": "plan_only"}, {"route": "continue"})["reason"] == "plan_only"
    )
    assert classify({"kind": "empty"}, {"route": "continue"})["reason"] == "zero_diff"


def _plan_only():
    return {"ok": False, "reason": "plan_only", "error": "refusing plan-only"}


def test_plan_only_never_reaches_push_or_pr_create(monkeypatch):
    def boom(main, argv):
        raise AssertionError("mutation must not run")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = {
        "worktree_add": {"worktree": "/tmp/w", "branch": "ai/x"},
        "make_branch": {"branch": "ai/x"},
        "commit_all": {"committed": True},
        "test_local": {"ok": True, "tested": True},
        "assert_real_diff": _plan_only(),
        "get_issue": {
            "issue": {
                "repo": "a/b",
                "number": 7,
                "title": "x",
                "body": "",
                "labels": [],
                "assignees": [],
                "url": "u",
            }
        },
        "push": {"ok": True},
    }
    assert (
        fala_organ._handle("push", {"repo": "a/b", "live": False}, up)["reason"]
        == "plan_only"
    )
    assert (
        fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)["reason"]
        == "plan_only"
    )


def test_push_without_real_diff_fails_and_manifest_conducts_gate(monkeypatch):
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda *a: (_ for _ in ()).throw(AssertionError("no push")),
    )
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/w", "branch": "b"},
            "commit_all": {"committed": True},
            "test_local": {"ok": True, "tested": True},
        },
    )
    assert result["reason"] == "real_diff_missing"
    path = next(
        p for p in describe_package()["paths"] if p["id"] == "issue_to_pr_delivery"
    )
    nodes = {n["id"]: n for n in path["nodes"]}
    assert (
        "assert_real_diff" in nodes["push"]["conduction"]
        and "assert_real_diff" in nodes["pr_create"]["conduction"]
    )
