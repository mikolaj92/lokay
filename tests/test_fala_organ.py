from pathlib import Path

from lokay import fala_organ


def _ok_test_local() -> dict:
    return {"ok": True, "tested": True, "skipped": False}


def _ok_real_diff() -> dict:
    return {"ok": True, "real": True, "kind": "real"}


def _skip_test_local() -> dict:
    return {
        "ok": True,
        "skipped": True,
        "reason": "no_python_test_suite",
        "tested": False,
    }


def _red_test_local() -> dict:
    return {"ok": False, "error": "local test suite failed"}


def _config(tmp_path: Path, *, required: bool, executor: bool) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: {str(executor).lower()}
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_checks: false
  require_llm_review: {str(required).lower()}
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )
    return str(path)


def test_pr_merge_pending_checks_wait_not_merge(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=True, executor=True)

    def boom(main, argv):
        raise AssertionError("pr_merge atom must not run while checks pending")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 9, "live": True},
        {
            "pr_checks": {"ok": True, "status": "pending", "merge_ok": False},
            "publish_pr_review": {
                "ok": True,
                "merge_ok": True,
                "decision": {"verdict": "approve", "secrets": False},
            },
        },
    )
    assert merged["skipped"] is True
    assert merged["reason"] == "checks_pending"
    assert merged["waiting"] is True


def test_pr_merge_secrets_fail_closed(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=True, executor=True)

    def boom(main, argv):
        raise AssertionError("pr_merge atom must not run on secrets")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 10, "live": True},
        {
            "pr_checks": {"ok": True, "status": "passed", "merge_ok": True},
            "publish_pr_review": {
                "ok": True,
                "merge_ok": False,
                "decision": {"verdict": "approve", "secrets": True},
            },
        },
    )
    assert merged["skipped"] is True
    assert merged["reason"] == "secrets"
    assert merged["needs_review"] is True


def _closed_issue_up() -> dict:
    return {
        "get_issue": {
            "issue": {
                "repo": "a/b",
                "number": 7,
                "state": "CLOSED",
            }
        }
    }


def test_closed_issue_skips_all_mutating_atoms_at_organ_boundary(monkeypatch):
    def boom(main, argv):
        raise AssertionError("closed issue must not invoke a mutating atom")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    for atom in ("commit_all", "push", "pr_create", "pr_merge"):
        result = fala_organ._handle(
            atom, {"repo": "a/b", "issue": 7}, _closed_issue_up()
        )
        assert result["ok"] is False
        assert result["reason"] == "issue_closed"


def test_live_closed_issue_skips_mutating_atoms_before_handlers(monkeypatch):
    def fake_run(main, argv):
        if "--head" in argv or "--worktree" in argv:
            raise AssertionError(
                "mutating handler must not run after live CLOSED re-view"
            )
        return {
            "ok": True,
            "issue": {"repo": "a/b", "number": 7, "state": "CLOSED"},
        }

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    push_up = {
        "get_issue": {"issue": {"repo": "a/b", "number": 7, "state": "OPEN"}},
        "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
        "commit_all": {"committed": True},
        "test_local": _ok_test_local(),
        "assert_real_diff": _ok_real_diff(),
    }
    for atom, inputs, up in (
        (
            "push",
            {"repo": "a/b", "issue": 7, "branch": "ai/fix/7-x", "live": True},
            push_up,
        ),
        (
            "pr_create",
            {"repo": "a/b", "issue": 7, "live": True},
            _pr_create_up(),
        ),
    ):
        result = fala_organ._handle(atom, inputs, up)
        assert result["ok"] is False
        assert result["reason"] == "issue_closed"


def test_live_closed_issue_skips_run_agent_before_handler(monkeypatch):
    def fake_run(main, argv):
        if "--issue" in argv:
            return {
                "ok": True,
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "state": "CLOSED",
                },
            }
        raise AssertionError("run_agent must not run after a live CLOSED re-view")

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "run_agent",
        {"repo": "a/b", "issue": 7, "live": True},
        {
            "get_issue": {"issue": {"repo": "a/b", "number": 7, "state": "OPEN"}},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"


def test_live_closed_issue_skips_repair_agent_before_handler(monkeypatch):
    def fake_run(main, argv):
        if "--issue" in argv:
            return {
                "ok": True,
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "state": "CLOSED",
                },
            }
        raise AssertionError("repair_agent must not run after a live CLOSED re-view")

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "issue": 7, "live": True},
        {
            "get_issue": {"issue": {"repo": "a/b", "number": 7, "state": "OPEN"}},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"


def test_closed_issue_does_not_block_read_only_atoms(monkeypatch):
    called = []

    def fake_run(main, argv):
        called.append(argv)
        return {"ok": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle("get_issue", {"repo": "a/b", "issue": 7}, {})
    assert result["ok"] is True
    assert called


def test_push_accepts_agent_created_unpublished_commit(monkeypatch):
    monkeypatch.setattr(fala_organ, "branch_ahead_of_upstream", lambda *a, **k: 2)
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {"ok": True, "pushed": True, "argv": argv},
    )

    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": False},
            "test_local": _ok_test_local(),
            "assert_real_diff": _ok_real_diff(),
        },
    )

    assert result["ok"] is True
    assert result["pushed"] is True


def test_push_rejects_true_zero_diff(monkeypatch):
    monkeypatch.setattr(fala_organ, "branch_ahead_of_upstream", lambda *a, **k: 0)

    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": False},
            "test_local": _ok_test_local(),
            "assert_real_diff": _ok_real_diff(),
        },
    )

    assert result["ok"] is False
    assert result["reason"] == "zero_diff"


def test_push_without_test_local_fails(monkeypatch):
    def boom(main, argv):
        raise AssertionError("push must not run without test_local conduction")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "test_local_missing"


def test_push_skipped_suite_still_pushes(monkeypatch):
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {"ok": True, "pushed": True},
    )
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": _skip_test_local(),
            "assert_real_diff": _ok_real_diff(),
        },
    )
    assert result["ok"] is True
    assert result["pushed"] is True


def test_push_red_suite_does_not_push(monkeypatch):
    def boom(main, argv):
        raise AssertionError("push must not run after red local tests")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": _red_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "test_local_failed"


def test_pr_merge_without_test_local_fails(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)

    def boom(main, argv):
        raise AssertionError("pr_merge must not run without test_local conduction")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {
            "pr_checks": {"ok": True, "status": "none", "merge_ok": True},
            "publish_pr_review": {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_required",
                "merge_ok": True,
            },
        },
    )
    assert merged["ok"] is False
    assert merged["reason"] == "test_local_missing"


def test_pr_merge_skipped_suite_still_merges(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)
    called = []

    def fake_run(main, argv):
        called.append((main, argv))
        return {"ok": True, "merged": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {
            "pr_checks": {"ok": True, "status": "none", "merge_ok": True},
            "publish_pr_review": {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_required",
                "merge_ok": True,
            },
            "test_local": _skip_test_local(),
        },
    )
    assert merged["merged"] is True
    assert called, "pr_merge atom must execute after skipped local suite"


def test_pr_merge_passes_issue_only_when_known(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)
    up = {
        "pr_checks": {"ok": True, "status": "none", "merge_ok": True},
        "publish_pr_review": {"ok": True, "merge_ok": True},
        "test_local": _ok_test_local(),
    }

    for issue in (23, None):
        called = []
        monkeypatch.setattr(
            fala_organ,
            "_run_atom_main",
            lambda main, argv: called.append(argv) or {"ok": True, "merged": True},
        )
        inputs = {"config_path": cfg, "repo": "a/b", "pr": 7, "live": False}
        if issue is not None:
            inputs["issue"] = issue

        merged = fala_organ._handle("pr_merge", inputs, up)

        assert merged["merged"] is True
        assert ("--issue" in called[0]) is (issue is not None)
        if issue is not None:
            assert called[0][called[0].index("--issue") + 1] == str(issue)


def test_pr_merge_red_suite_does_not_merge(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)

    def boom(main, argv):
        raise AssertionError("pr_merge must not run after red local tests")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {
            "pr_checks": {"ok": True, "status": "none", "merge_ok": True},
            "publish_pr_review": {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_required",
                "merge_ok": True,
            },
            "test_local": _red_test_local(),
        },
    )
    assert merged["ok"] is False
    assert merged["reason"] == "test_local_failed"


def _pr_create_up() -> dict:
    return {
        "get_issue": {
            "issue": {
                "repo": "a/b",
                "number": 7,
                "title": "Fix thing",
                "body": "",
                "labels": [],
                "assignees": [],
                "url": "https://example.test/7",
            }
        },
        "make_branch": {"branch": "ai/fix/7-x"},
        "run_agent": {"ok": True, "stdout_tail": "done"},
        "test_local": _ok_test_local(),
        "assert_real_diff": _ok_real_diff(),
        "push": {"ok": True, "planned": True},
    }


def test_pr_create_without_test_local_fails(monkeypatch):
    def boom(main, argv):
        raise AssertionError("pr_create must not run without test_local conduction")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    del up["test_local"]
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "test_local_missing"


def test_pr_create_with_only_finalize_publish_goes(monkeypatch):
    called = []
    monkeypatch.setattr(
        "lokay.proc.pr_create_subflow.run",
        lambda **kwargs: called.append(kwargs) or {"ok": True, "pr": 1},
    )
    up = _pr_create_up()
    del up["test_local"]
    up["finalize_local_tests"] = {"ok": True, "route": "publish"}
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is True and called


def test_pr_create_red_test_local_never_creates(monkeypatch):
    def boom(main, argv):
        raise AssertionError("gh pr create must never run after a red test_local")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    up["test_local"] = _red_test_local()
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "test_local_failed"


def test_pr_create_red_recheck_never_creates(monkeypatch):
    def boom(main, argv):
        raise AssertionError("gh pr create must never run after a red recheck")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    up["test_local_recheck"] = _red_test_local()
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "test_local_recheck_failed"


def test_pr_create_without_push_fails(monkeypatch):
    def boom(main, argv):
        raise AssertionError("pr_create must not run without push conduction")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    del up["push"]
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "push_missing"


def test_pr_create_failed_push_never_creates(monkeypatch):
    def boom(main, argv):
        raise AssertionError("gh pr create must never run after a refused push")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    up["push"] = {"ok": False, "error": "push rejected", "reason": "zero_diff"}
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "push_failed"


def test_pr_create_passes_issue_number_to_authored_subflow(monkeypatch):
    called = []
    monkeypatch.setattr(
        "lokay.proc.pr_create_subflow.run",
        lambda **kwargs: called.append(kwargs) or {"ok": True, "pr": 1},
    )
    result = fala_organ._handle(
        "pr_create", {"repo": "a/b", "live": False}, _pr_create_up()
    )
    assert result["ok"] is True and called[0]["issue"] == 7


def test_pr_create_does_not_open_when_issue_already_closed(monkeypatch):
    def boom(main, argv):
        raise AssertionError("pr_create must not run after the issue closed")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    up = _pr_create_up()
    up["get_issue"]["issue"]["state"] = "CLOSED"
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, up)
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"


def test_pr_create_rechecks_live_issue_before_opening(monkeypatch):
    def fake_run(main, argv):
        if "--issue" in argv:
            return {
                "ok": True,
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix thing",
                    "state": "CLOSED",
                },
            }
        raise AssertionError("gh pr create must not run after a live CLOSED re-view")

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "pr_create", {"repo": "a/b", "live": True}, _pr_create_up()
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"


def test_pr_create_runs_authored_subflow_when_live_issue_still_open(monkeypatch):
    called = []

    def fake_run(main, argv):
        return {
            "ok": True,
            "issue": {
                "repo": "a/b",
                "number": 7,
                "title": "Fix thing",
                "state": "OPEN",
            },
        }

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    monkeypatch.setattr(
        "lokay.proc.pr_create_subflow.run",
        lambda **kwargs: called.append(kwargs) or {"ok": True, "pr": 1},
    )
    result = fala_organ._handle(
        "pr_create", {"repo": "a/b", "live": True}, _pr_create_up()
    )
    assert result["ok"] is True and called[0]["head"]


def test_repair_agent_treats_missing_live_issue_as_closed(monkeypatch):
    def fake_run(main, argv):
        if "--issue" in argv:
            return {"ok": False, "error": "issue not found: a/b#7"}
        raise AssertionError("timeout-resume must not run after the issue vanished")

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "issue": 7, "live": True},
        {
            "get_issue": {
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix x",
                    "state": "OPEN",
                }
            },
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "run_agent": {"ok": True, "timed_out": True, "reason": "timeout"},
            "test_local": _ok_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"
    assert result["issue_state"] == "MISSING"


def test_push_red_recheck_does_not_push(monkeypatch):
    def boom(main, argv):
        raise AssertionError("push must not run after a red recheck")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": _ok_test_local(),
            "test_local_recheck": _red_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "test_local_recheck_failed"


def test_push_green_recheck_pushes(monkeypatch):
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {"ok": True, "pushed": True},
    )
    result = fala_organ._handle(
        "push",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": _red_test_local(),
            "test_local_recheck": _ok_test_local(),
            "assert_real_diff": _ok_real_diff(),
        },
    )
    assert result["ok"] is True
    assert result["pushed"] is True


def test_localize_forwards_plan_files_likely_to_nested_subflow(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        "lokay.proc.localize_execution_subflow.run",
        lambda **kwargs: captured.update(kwargs) or {"ok": True, "paths": ["src/a.py"]},
    )
    result = fala_organ._handle(
        "localize",
        {"repo": "a/b", "issue": 7, "live": False},
        {
            "get_issue": {
                "issue": {"repo": "a/b", "number": 7, "title": "Fix a", "body": ""}
            },
            "worktree_add": {"worktree": str(tmp_path)},
            "plan_issue": {"plan": {"files_likely": ["src/a.py", "tests/test_a.py"]}},
        },
    )
    assert result["ok"] and captured["extra_inputs"]["plan"]["plan"][
        "files_likely"
    ] == ["src/a.py", "tests/test_a.py"]


def test_repair_agent_does_not_resume_when_issue_already_closed(monkeypatch):
    def boom(main, argv):
        raise AssertionError("timeout-resume must not run after the issue closed")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "issue": 7, "live": False},
        {
            "get_issue": {
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix x",
                    "state": "CLOSED",
                }
            },
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "run_agent": {"ok": True, "timed_out": True, "reason": "timeout"},
            "test_local": _ok_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"
    assert result["issue_state"] == "CLOSED"


def test_repair_agent_rechecks_live_issue_before_timeout_resume(monkeypatch):
    def fake_run(main, argv):
        if "--issue" in argv:
            return {
                "ok": True,
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix x",
                    "state": "CLOSED",
                },
            }
        raise AssertionError("timeout-resume must not run after a live CLOSED re-view")

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "issue": 7, "live": True},
        {
            "get_issue": {
                "issue": {
                    "repo": "a/b",
                    "number": 7,
                    "title": "Fix x",
                    "state": "OPEN",
                }
            },
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "run_agent": {"ok": True, "timed_out": True, "reason": "timeout"},
            "test_local": _ok_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "issue_closed"
    assert result["issue_state"] == "CLOSED"


def test_repair_agent_runs_after_localize_found_paths(monkeypatch):
    called = []

    def fake_run(main, argv):
        called.append(argv)
        return {"ok": True, "status": "completed"}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "issue": 7, "live": True},
        {
            "get_issue": {"issue": {"repo": "a/b", "number": 7, "title": "Fix x"}},
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "run_agent": {
                "ok": False,
                "reason": "agent_failed",
                "localize": {"ok": True, "paths": ["src/a.py"]},
            },
            "test_local": _red_test_local(),
        },
    )
    assert result["ok"] is True
    assert result["attempted"] is True
    assert called


def test_repair_agent_refused_in_pr_repair_mode(monkeypatch):
    def boom(main, argv):
        raise AssertionError("no nested repair session on the pr_repair lane")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "repair_agent",
        {
            "repo": "a/b",
            "branch": "ai/fix/7-x",
            "live": True,
            "mode": "repair",
            "pr": 3,
        },
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "test_local": _red_test_local(),
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "repair_agent_not_allowed"


def test_repair_agent_red_probe_runs_one_patch_from_log(monkeypatch):
    captured: dict = {}

    def fake_run(main, argv):
        prompt_path = argv[argv.index("--prompt-file") + 1]
        captured["prompt"] = Path(prompt_path).read_text(encoding="utf-8")
        captured["argv"] = argv
        return {"ok": True, "status": "completed"}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    red = {
        "ok": False,
        "error": "local test suite failed",
        "stdout_tail": "FAILED tests/test_x.py::test_y - assert 1 == 2",
        "stderr_tail": "",
    }
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "issue": 7, "live": True},
        {
            "get_issue": {"issue": {"repo": "a/b", "number": 7, "title": "Fix x"}},
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "test_local": red,
        },
    )
    assert result["ok"] is True
    assert result["attempted"] is True
    assert "--worktree" in captured["argv"]
    assert "FAILED tests/test_x.py::test_y" in captured["prompt"]
    assert "K=1" in captured["prompt"]


def test_rebase_onto_base_forwards_repo(monkeypatch):
    captured = []

    def fake_run(main, argv):
        captured.append(argv)
        return {"ok": True, "rebased": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "rebase_onto_base",
        {"repo": "mikolaj92/lokay", "live": True},
        {"worktree_add": {"worktree": "/tmp/worktree"}},
    )
    assert result["ok"] is True
    assert captured
    argv = captured[0]
    assert argv[argv.index("--repo") + 1] == "mikolaj92/lokay"
    assert argv[argv.index("--worktree") + 1] == "/tmp/worktree"


def test_push_forwards_repo(monkeypatch):
    captured = []

    def fake_run(main, argv):
        captured.append(argv)
        return {"ok": True, "pushed": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "push",
        {"repo": "mikolaj92/lokay", "branch": "ai/fix/7-x", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "commit_all": {"committed": True},
            "test_local": _ok_test_local(),
            "assert_real_diff": _ok_real_diff(),
        },
    )
    assert result["ok"] is True
    assert captured
    argv = captured[0]
    assert argv[argv.index("--repo") + 1] == "mikolaj92/lokay"
    assert argv[argv.index("--worktree") + 1] == "/tmp/worktree"
    assert argv[argv.index("--branch") + 1] == "ai/fix/7-x"


def test_test_local_dispatches_nested_subflow(monkeypatch):
    captured = []
    monkeypatch.setattr(
        "lokay.proc.test_local_execution_subflow.run",
        lambda **kwargs: captured.append(kwargs) or {"ok": True, "tested": True},
    )
    result = fala_organ._handle(
        "test_local",
        {"changed_scope": True},
        {"worktree_add": {"worktree": "/tmp/worktree"}},
    )
    assert result["ok"] is True
    assert captured[0]["worktree"] == "/tmp/worktree"
    assert captured[0]["changed_scope"] is True


def test_ensure_project_cwd_prefers_lokay_root(tmp_path, monkeypatch):
    root = tmp_path / "lokay"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='lokay'\n", encoding="utf-8")
    (root / "fala").mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("LOKAY_ROOT", str(root))
    monkeypatch.chdir(elsewhere)
    fala_organ._ensure_project_cwd()
    assert Path.cwd() == root.resolve()


def test_bundled_fala_manifest_is_ascii_safe():
    """Native TOML parsing must never land on a UTF-8 continuation byte."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    authored = (root / "fala" / "lokay.fala-package.toml").read_bytes()
    bundled = (root / "src" / "lokay" / "data" / "lokay.fala-package.toml").read_bytes()
    assert authored == bundled
    authored.decode("ascii")


def test_organ_envelope_keeps_fallback_status_failed():
    from lokay.fala_organ import organ_envelope

    out = organ_envelope(
        "run_localization_agent",
        {"ok": True, "route": "fallback", "status": "failed", "text": ""},
    )
    assert out["ok"] is True
    assert out["route"] == "fallback"
    assert out["status"] == "failed"


def test_organ_envelope_still_raises_on_not_ok():
    from lokay.fala_organ import organ_envelope
    import pytest

    with pytest.raises(RuntimeError) as caught:
        organ_envelope("run_agent", {"ok": False, "status": "failed", "error": "agent failed"})
    assert "agent failed" in str(caught.value)
