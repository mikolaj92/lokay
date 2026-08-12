from pathlib import Path

from lokay import fala_organ


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
        {"pr_checks": {"ok": True, "status": "none", "merge_ok": True}, "pr_review": review},
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
        },
    )

    assert result["ok"] is False
    assert result["reason"] == "zero_diff"


def test_bundled_fala_manifest_is_ascii_safe():
    """Native TOML parsing must never land on a UTF-8 continuation byte."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    authored = (root / "fala" / "lokay.fala-package.toml").read_bytes()
    bundled = (root / "src" / "lokay" / "data" / "lokay.fala-package.toml").read_bytes()
    assert authored == bundled
    authored.decode("ascii")
