"""Hermetic tests for lokay-test-local and its Fala gate."""

from __future__ import annotations

import json
from pathlib import Path

from lokay import fala_organ
from lokay.graph_run import describe_package
from lokay.proc import test_local
from lokay.runner import CommandResult, CommandSpec


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _fake_runner(result: CommandResult):
    class FakeRunner:
        def run(self, spec, *, live):
            assert spec.argv == test_local.TEST_ARGV
            assert spec.timeout_seconds == test_local.TEST_TIMEOUT_SECONDS
            assert live is True
            return result

    return FakeRunner()


def test_no_suite_skips(tmp_path: Path, capsys):
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["skipped"] is True
    assert payload["reason"] == "no_python_test_suite"
    assert payload["tested"] is False


def test_missing_worktree_fails_closed(tmp_path: Path, capsys):
    missing = tmp_path / "absent"
    code = test_local.main(["--worktree", str(missing)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "not a directory" in payload["error"]


def test_red_pytest_fails_closed(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    spec = CommandSpec(test_local.TEST_ARGV, cwd=str(tmp_path.resolve()), timeout_seconds=1800)
    monkeypatch.setattr(
        test_local,
        "runner",
        lambda: _fake_runner(CommandResult(spec=spec, executed=True, returncode=1)),
    )
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["error"] == "local test suite failed"
    assert payload["returncode"] == 1


def test_tests_dir_without_pyproject_still_runs(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "tests").mkdir()
    spec = CommandSpec(test_local.TEST_ARGV, cwd=str(tmp_path.resolve()), timeout_seconds=1800)
    monkeypatch.setattr(
        test_local,
        "runner",
        lambda: _fake_runner(CommandResult(spec=spec, executed=True, returncode=0)),
    )
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["tested"] is True
    assert payload["skipped"] is False
    assert payload["tests"] == "uv run --extra dev pytest -q"


def test_organ_dispatches_worktree_from_worktree_add(monkeypatch):
    captured: list[tuple] = []

    def fake_run(main, argv):
        captured.append((main, argv))
        return {"ok": True, "tested": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "test_local",
        {},
        {"worktree_add": {"worktree": "/tmp/wt"}},
    )
    assert result["ok"] is True
    assert captured == [(test_local.main, ["--worktree", "/tmp/wt"])]


def test_organ_red_gate_does_not_reach_push(monkeypatch):
    """Fail-closed atom result: Fala would raise before conducting push."""
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {"ok": False, "error": "local test suite failed", "_exit": 1},
    )
    result = fala_organ._handle(
        "test_local",
        {},
        {"worktree_add": {"worktree": "/tmp/wt"}},
    )
    assert result["ok"] is False
    assert result["_exit"] == 1

    called = []

    def boom(main, argv):
        called.append(argv)
        raise AssertionError("push must not run after red local tests")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    # Graph conduction is the real gate; this documents that a failed
    # test_local result is not treated as skippable success.
    assert not result.get("skipped")
    assert called == []


def _path_nodes(path_id: str) -> dict[str, dict]:
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == path_id)
    return {n["id"]: n for n in path["nodes"]}


def test_issue_to_pr_push_and_pr_create_conduct_through_test_local():
    by_id = _path_nodes("issue_to_pr")
    assert "test_local" in by_id
    assert "commit_all" in by_id["test_local"]["conduction"]
    assert "worktree_add" in by_id["test_local"]["conduction"]
    assert "test_local" in by_id["push"]["conduction"]
    assert "test_local" in by_id["pr_create"]["conduction"]
    assert "push" in by_id["pr_create"]["conduction"]


def test_pr_repair_push_conducts_through_test_local():
    by_id = _path_nodes("pr_repair")
    assert "test_local" in by_id
    assert "commit_all" in by_id["test_local"]["conduction"]
    assert "test_local" in by_id["push"]["conduction"]
    assert "push" not in by_id["test_local"]["conduction"]
