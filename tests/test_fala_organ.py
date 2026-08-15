from pathlib import Path

from lokay import fala_organ


def _ok_test_local() -> dict:
    return {"ok": True, "tested": True, "skipped": False}


def _ok_real_diff() -> dict:
    return {"ok": True, "real": True, "kind": "real"}


def _skip_test_local() -> dict:
    return {"ok": True, "skipped": True, "reason": "no_python_test_suite", "tested": False}


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


def test_review_not_required_bypasses_disabled_executor_and_allows_merge(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=False, executor=False)
    review = fala_organ._handle(
        "pr_review",
        {"config_path": cfg, "repo": "a/b", "pr": 7, "live": True},
        {"pr_checks": {"ok": True, "status": "none"}},
    )
    assert review == {
        "ok": True,
        "skipped": True,
        "reason": "llm_review_not_required",
        "merge_ok": True,
        "repo": "a/b",
        "pr": 7,
    }

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
            "pr_review": review,
            "test_local": _ok_test_local(),
        },
    )
    assert merged["merged"] is True
    assert called, "pr_merge atom must execute"


def test_required_review_with_disabled_executor_stays_blocked(tmp_path, monkeypatch):
    cfg = _config(tmp_path, required=True, executor=False)

    def fake_run(main, argv):
        return {"ok": True, "skipped": True, "reason": "executor_disabled", "merge_ok": False}
    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    review = fala_organ._handle(
        "pr_review",
        {"config_path": cfg, "repo": "a/b", "pr": 8, "live": True},
        {"pr_checks": {"ok": True, "status": "none"}},
    )
    merged = fala_organ._handle(
        "pr_merge",
        {"config_path": cfg, "repo": "a/b", "pr": 8, "live": True},
        {"pr_checks": {"ok": True, "status": "none", "merge_ok": True}, "pr_review": review},
    )
    assert merged["skipped"] is True
    assert merged["reason"] == "executor_disabled"


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
            "pr_review": {
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
            "pr_review": {
                "ok": True,
                "merge_ok": False,
                "decision": {"verdict": "approve", "secrets": True},
            },
        },
    )
    assert merged["skipped"] is True
    assert merged["reason"] == "secrets"
    assert merged["needs_review"] is True


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
            "pr_review": {
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
            "pr_review": {
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
            "pr_review": {
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


def test_pr_create_green_tests_and_successful_push_runs(monkeypatch):
    called = []

    def fake_run(main, argv):
        called.append(argv)
        return {"ok": True, "pr": {"url": "https://example.test/pr/1"}}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle("pr_create", {"repo": "a/b", "live": False}, _pr_create_up())
    assert result["ok"] is True
    assert called and "--head" in called[0]


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


def test_repair_agent_skips_when_first_probe_green(monkeypatch):
    def boom(main, argv):
        raise AssertionError("repair agent must not run after a green test_local")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "test_local": _ok_test_local(),
        },
    )
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "test_local_ok"


def test_repair_agent_skips_when_suite_absent(monkeypatch):
    def boom(main, argv):
        raise AssertionError("repair agent must not run when there is no test suite")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"},
            "test_local": _skip_test_local(),
        },
    )
    assert result["ok"] is True
    assert result["skipped"] is True


def test_repair_agent_without_test_local_fails(monkeypatch):
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True},
        {"worktree_add": {"worktree": "/tmp/worktree", "branch": "ai/fix/7-x"}},
    )
    assert result["ok"] is False
    assert result["reason"] == "test_local_missing"


def test_repair_agent_refused_in_pr_repair_mode(monkeypatch):
    def boom(main, argv):
        raise AssertionError("no nested repair session on the pr_repair lane")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "repair_agent",
        {"repo": "a/b", "branch": "ai/fix/7-x", "live": True, "mode": "repair", "pr": 3},
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


def test_recheck_skips_when_first_probe_green(monkeypatch):
    def boom(main, argv):
        raise AssertionError("recheck must not rerun a green suite")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "test_local_recheck",
        {"repo": "a/b", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree"},
            "test_local": _ok_test_local(),
            "repair_agent": {"ok": True, "skipped": True, "reason": "test_local_ok"},
        },
    )
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "test_local_ok"


def test_recheck_fails_closed_when_repair_agent_failed(monkeypatch):
    def boom(main, argv):
        raise AssertionError("recheck must not rerun after a failed repair agent")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    result = fala_organ._handle(
        "test_local_recheck",
        {"repo": "a/b", "live": False},
        {
            "worktree_add": {"worktree": "/tmp/worktree"},
            "test_local": _red_test_local(),
            "repair_agent": {"ok": False, "error": "agent crashed"},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "repair_agent_failed"


def test_recheck_zero_diff_repair_fails_closed(monkeypatch):
    def boom(main, argv):
        raise AssertionError("recheck must not rerun when the repair patch is zero-diff")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    monkeypatch.setattr(fala_organ, "branch_ahead_of_upstream", lambda *a, **k: 0)
    result = fala_organ._handle(
        "test_local_recheck",
        {"repo": "a/b", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree"},
            "commit_all": {"committed": False},
            "test_local": _red_test_local(),
            "repair_agent": {"ok": True, "attempted": True},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "zero_diff"


def test_recheck_reruns_once_after_committed_repair(monkeypatch):
    captured = []

    def fake_run(main, argv):
        captured.append(argv)
        return {"ok": True, "tested": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    monkeypatch.setattr(fala_organ, "branch_ahead_of_upstream", lambda *a, **k: 1)
    result = fala_organ._handle(
        "test_local_recheck",
        {"repo": "a/b", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree"},
            "commit_all": {"committed": False},
            "test_local": _red_test_local(),
            "repair_agent": {"ok": True, "attempted": True},
        },
    )
    assert result["ok"] is True
    assert result["recheck"] is True
    assert captured == [["--worktree", "/tmp/worktree"]]


def test_recheck_red_marks_bounded_loop_exhausted(monkeypatch):
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {
            "ok": False,
            "error": "local test suite failed",
            "stdout_tail": "x" * 5000,
            "_exit": 1,
        },
    )
    monkeypatch.setattr(fala_organ, "branch_ahead_of_upstream", lambda *a, **k: 1)
    result = fala_organ._handle(
        "test_local_recheck",
        {"repo": "a/b", "live": True},
        {
            "worktree_add": {"worktree": "/tmp/worktree"},
            "commit_all": {"committed": False},
            "test_local": _red_test_local(),
            "repair_agent": {"ok": True, "attempted": True},
        },
    )
    assert result["ok"] is False
    assert result["reason"] == "local_repair_exhausted"
    assert result["recheck"] is True
    # Machine reason must precede the big log tail so the organ's truncated
    # failure raise still carries it.
    assert list(result).index("reason") < list(result).index("stdout_tail")


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
