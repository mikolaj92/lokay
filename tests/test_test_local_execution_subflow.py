"""test_local_execution uses a per-issue journal, not local/test."""

from lokay.proc import test_local_execution_subflow


def test_subflow_passes_repo_and_issue_from_worktree(monkeypatch, tmp_path):
    captured = []

    def fake_path(**kwargs):
        captured.append(kwargs)
        return {"ok": True, "skipped": True, "reason": "no_declared_test"}

    monkeypatch.setattr("lokay.proc.test_local_execution_subflow.run_path", fake_path)
    worktree = tmp_path / "ai__fix__5191-posejdon-leftover"
    worktree.mkdir()
    out = test_local_execution_subflow.run(
        worktree=str(worktree),
        changed_scope=False,
        repo="mikolaj92/Temida",
        issue=5191,
    )
    assert captured[0]["path_id"] == "test_local_execution"
    assert captured[0]["repo"] == "mikolaj92/Temida"
    assert captured[0]["issue"] == 5191
    assert captured[0]["extra_inputs"]["worktree"] == str(worktree)
    assert out["ok"] is True


def test_subflow_parses_issue_from_worktree_when_issue_omitted(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setattr(
        "lokay.proc.test_local_execution_subflow.run_path",
        lambda **kwargs: captured.append(kwargs) or {"ok": True},
    )
    worktree = tmp_path / "ai__fix__186-host_run_package"
    worktree.mkdir()
    test_local_execution_subflow.run(
        worktree=str(worktree),
        changed_scope=False,
        repo="mikolaj92/Fala",
    )
    assert captured[0]["repo"] == "mikolaj92/Fala"
    assert captured[0]["issue"] == 186
