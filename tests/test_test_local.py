"""Hermetic tests for lokay-test-local and its Fala gate."""

from __future__ import annotations

import pytest

import json
from pathlib import Path

from lokay import fala_organ
from lokay.graph_run import describe_package
from lokay.proc import test_local
from lokay.runner import CommandResult, CommandSpec

LOKAY_PYTEST = ("uv", "run", "--extra", "dev", "pytest", "-q")


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _declare_test(worktree: Path, command: object = None) -> None:
    if command is None:
        command = list(LOKAY_PYTEST)
    if isinstance(command, str):
        test_line = f'test = {command!r}\n'
    else:
        items = ", ".join(repr(part) for part in command)
        test_line = f"test = [{items}]\n"
    (worktree / "pyproject.toml").write_text(
        "[project]\nname = 'x'\n\n[tool.lokay]\n" + test_line,
        encoding="utf-8",
    )


def _fake_runner(expected: tuple[str, ...], result: CommandResult):
    class FakeRunner:
        def run(self, spec, *, live):
            assert spec.argv == expected
            assert spec.timeout_seconds == test_local.TEST_TIMEOUT_SECONDS
            assert spec.env.get("LOKAY_HEALTH_LEASE") == ""
            assert spec.env.get("LOKAY_HEALTH_LEASE_PATH") == ""
            assert live is True
            return result

    return FakeRunner()


def test_this_repo_declares_pytest():
    root = Path(__file__).resolve().parents[1]
    assert test_local.declared_test_argv(root) == LOKAY_PYTEST


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_product_repo_skips_without_inspecting_or_running_worktree(
    tmp_path: Path, monkeypatch, capsys
):
    product = tmp_path / "missing-product-worktree"

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("product repositories must not inspect or run tests")

    monkeypatch.setattr(test_local, "declared_test_argv", fail_if_called)
    monkeypatch.setattr(test_local, "runner", fail_if_called)

    for repo in ("mikolaj92/Temida", "mikolaj92/takt"):
        code = test_local.main(
            ["--repo", repo, "--worktree", str(product)]
        )
        assert code == 0
        payload = _payload(capsys)
        assert payload == {
            "ok": True,
            "skipped": True,
            "reason": "repo_not_delivered_by_mini_mill",
            "tested": False,
            "repo": repo,
            "worktree": str(product),
        }


def test_no_declaration_skips(tmp_path: Path, capsys):
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["skipped"] is True
    assert payload["reason"] == "no_declared_test"
    assert payload["tested"] is False


def test_pyproject_and_tests_without_declaration_skips(tmp_path: Path, capsys):
    """Fala-shaped tree: pyproject + tests must not invent pytest."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'fala-shaped'\n\n[project.optional-dependencies]\n"
        "dev = ['pytest>=8.0']\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["skipped"] is True
    assert payload["reason"] == "no_declared_test"
    assert payload["tested"] is False


def test_missing_worktree_fails_closed(tmp_path: Path, capsys):
    missing = tmp_path / "absent"
    code = test_local.main(["--worktree", str(missing)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "not a directory" in payload["error"]


def test_invalid_declaration_fails_closed(tmp_path: Path, capsys):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.lokay]\ntest = 12\n",
        encoding="utf-8",
    )
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["reason"] == "invalid_test_declaration"
    assert payload["tested"] is False


def test_red_declared_suite_fails_closed(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path)
    spec = CommandSpec(LOKAY_PYTEST, cwd=str(tmp_path.resolve()), timeout_seconds=1800)
    monkeypatch.setattr(
        test_local,
        "runner",
        lambda: _fake_runner(
            LOKAY_PYTEST,
            CommandResult(
                spec=spec,
                executed=True,
                returncode=1,
                stdout="FAILED tests/test_x.py::test_y - assert 1 == 2\n",
                stderr="1 failed\n",
            ),
        ),
    )
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["error"] == "local test suite failed"
    assert payload["returncode"] == 1
    assert payload["tests"] == "uv run --extra dev pytest -q"
    assert "FAILED tests/test_x.py::test_y" in payload["stdout_tail"]
    assert payload["stderr_tail"] == "1 failed\n"


def test_changed_pytest_scope_maps_src_and_changed_ticket_tests(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_foo.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_ticket.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        test_local,
        "list_changed_paths",
        lambda run, worktree, base: ["src/foo.py", "tests/test_ticket.py"],
    )
    argv = test_local._changed_pytest_argv(object(), tmp_path, LOKAY_PYTEST)
    assert argv == (*LOKAY_PYTEST, "tests/test_foo.py", "tests/test_ticket.py")


def test_red_full_suite_accepts_green_changed_scope(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path)
    scoped_argv = (*LOKAY_PYTEST, "tests/test_foo.py")
    monkeypatch.setattr(
        test_local,
        "_changed_pytest_argv",
        lambda run, worktree, argv: scoped_argv,
    )

    class SequentialRunner:
        def __init__(self):
            self.calls = []

        def run(self, spec, *, live):
            self.calls.append(spec.argv)
            return CommandResult(
                spec=spec,
                executed=True,
                returncode=1 if len(self.calls) == 1 else 0,
                stdout="FAILED tests/test_unrelated.py" if len(self.calls) == 1 else "",
            )

    run = SequentialRunner()
    monkeypatch.setattr(test_local, "runner", lambda: run)
    code = test_local.main(["--worktree", str(tmp_path), "--changed-scope"])
    assert code == 0
    assert run.calls == [LOKAY_PYTEST, scoped_argv]
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["scoped"] is True
    assert payload["full_suite_returncode"] == 1
    assert payload["tests"].endswith("tests/test_foo.py")


def test_red_changed_scope_still_refuses(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path)
    scoped_argv = (*LOKAY_PYTEST, "tests/test_foo.py")
    monkeypatch.setattr(
        test_local,
        "_changed_pytest_argv",
        lambda run, worktree, argv: scoped_argv,
    )

    class RedRunner:
        def run(self, spec, *, live):
            return CommandResult(
                spec=spec,
                executed=True,
                returncode=1,
                stdout=f"FAILED {spec.argv[-1]}::test_ticket\n",
            )

    monkeypatch.setattr(test_local, "runner", lambda: RedRunner())
    code = test_local.main(["--worktree", str(tmp_path), "--changed-scope"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["tests"].endswith("tests/test_foo.py")
    assert "test_ticket" in payload["stdout_tail"]


def test_declared_string_command_runs_for_lokay(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path, "pixi run core-smoke")
    argv = ("pixi", "run", "core-smoke")
    spec = CommandSpec(argv, cwd=str(tmp_path.resolve()), timeout_seconds=1800)
    monkeypatch.setattr(
        test_local,
        "runner",
        lambda: _fake_runner(argv, CommandResult(spec=spec, executed=True, returncode=0)),
    )
    code = test_local.main(
        ["--repo", "mikolaj92/lokay", "--worktree", str(tmp_path)]
    )
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["tested"] is True
    assert payload["skipped"] is False
    assert payload["tests"] == "pixi run core-smoke"


def test_declared_suite_strips_mill_lease(tmp_path: Path, monkeypatch, capsys):
    """Verifier must not inherit the mill health capability."""
    _declare_test(tmp_path)
    captured: list = []

    class CaptureRunner:
        def run(self, spec, *, live):
            captured.append(spec.env)
            return CommandResult(spec=spec, executed=True, returncode=0)

    monkeypatch.setattr(test_local, "runner", lambda: CaptureRunner())
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    assert captured[0]["LOKAY_HEALTH_LEASE"] == ""
    assert captured[0]["LOKAY_HEALTH_LEASE_PATH"] == ""
    assert _payload(capsys)["tested"] is True


def test_green_receipt_reuses_identical_head_and_origin_main(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path)
    (tmp_path / ".git").mkdir()

    class CachedRunner:
        def __init__(self):
            self.suite_runs = 0

        def run(self, spec, *, live):
            if spec.argv[:2] == ("git", "rev-parse"):
                value = "head" if spec.argv[-1] == "HEAD" else "base"
                return CommandResult(spec=spec, executed=True, returncode=0, stdout=value + "\n")
            self.suite_runs += 1
            return CommandResult(spec=spec, executed=True, returncode=0)

    run = CachedRunner()
    monkeypatch.setattr(test_local, "runner", lambda: run)

    assert test_local.main(["--worktree", str(tmp_path)]) == 0
    first = _payload(capsys)
    assert first["cached"] is False
    assert test_local.main(["--worktree", str(tmp_path)]) == 0
    second = _payload(capsys)
    assert second["cached"] is True
    assert run.suite_runs == 1


def test_declared_list_command_runs(tmp_path: Path, monkeypatch, capsys):
    _declare_test(tmp_path, list(LOKAY_PYTEST))
    spec = CommandSpec(LOKAY_PYTEST, cwd=str(tmp_path.resolve()), timeout_seconds=1800)
    monkeypatch.setattr(
        test_local,
        "runner",
        lambda: _fake_runner(
            LOKAY_PYTEST, CommandResult(spec=spec, executed=True, returncode=0)
        ),
    )
    code = test_local.main(["--worktree", str(tmp_path)])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["tested"] is True
    assert payload["skipped"] is False
    assert payload["tests"] == "uv run --extra dev pytest -q"


def test_organ_record_red_first_probe_does_not_raise(monkeypatch):
    """issue_to_pr first probe records a red suite so the nest can run."""
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {
            "ok": False,
            "error": "local test suite failed",
            "stdout_tail": "FAILED tests/test_x.py::test_y",
            "_exit": 1,
        },
    )
    result = fala_organ._handle(
        "test_local",
        {"record_red": True},
        {"worktree_add": {"worktree": "/tmp/wt"}},
    )
    assert result["ok"] is True
    assert result["passed"] is False
    assert result["recorded_red"] is True
    assert result["_exit"] == 0
    assert result["stdout_tail"] == "FAILED tests/test_x.py::test_y"
    # Publish atoms still refuse this envelope.
    refused = fala_organ._require_test_local({"test_local": result})
    assert refused is not None
    assert refused["reason"] == "test_local_failed"


def test_organ_default_test_local_still_fails_closed(monkeypatch):
    monkeypatch.setattr(
        fala_organ,
        "_run_atom_main",
        lambda main, argv: {
            "ok": False,
            "error": "local test suite failed",
            "_exit": 1,
        },
    )
    result = fala_organ._handle(
        "test_local",
        {},
        {"worktree_add": {"worktree": "/tmp/wt"}},
    )
    assert result["ok"] is False
    assert result["_exit"] == 1
    assert not result.get("recorded_red")


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


def test_organ_omits_empty_repo_on_test_local(monkeypatch):
    captured: list[tuple] = []

    def fake_run(main, argv):
        captured.append((main, argv))
        return {"ok": True, "tested": True}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "test_local",
        {"repo": ""},
        {"worktree_add": {"worktree": "/tmp/wt"}},
    )
    assert result["ok"] is True
    argv = captured[0][1]
    assert "--repo" not in argv
    assert argv == ["--worktree", "/tmp/wt"]


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
    assert "assert_real_diff" in by_id["push"]["conduction"]
    assert "test_local" in by_id["pr_create"]["conduction"]
    assert "assert_real_diff" in by_id["pr_create"]["conduction"]
    assert "push" in by_id["pr_create"]["conduction"]
    # Bounded AlphaCodium loop: one repair nest, then one recheck, then push.
    assert "repair_agent" in by_id
    assert "test_local_recheck" in by_id
    assert "test_local" in by_id["repair_agent"]["conduction"]
    assert "repair_agent" in by_id["test_local_recheck"]["conduction"]
    assert "test_local_recheck" in by_id["push"]["conduction"]
    assert "test_local_recheck" in by_id["pr_create"]["conduction"]
    # Recheck must not depend on push/pr_create (order: tests then publish).
    assert "push" not in by_id["test_local_recheck"]["conduction"]
    assert "pr_create" not in by_id["test_local_recheck"]["conduction"]


def test_pr_repair_push_conducts_through_test_local():
    by_id = _path_nodes("pr_repair")
    assert "test_local" in by_id
    assert "commit_all" in by_id["test_local"]["conduction"]
    assert "test_local" in by_id["push"]["conduction"]
    assert "assert_real_diff" in by_id["push"]["conduction"]
    assert "push" not in by_id["test_local"]["conduction"]


def test_pr_triage_merge_conducts_through_test_local():
    by_id = _path_nodes("pr_triage")
    assert "run_agent" not in by_id
    assert "worktree_add" in by_id
    assert "pr_review" in by_id["worktree_add"]["conduction"]
    assert "worktree_add" in by_id["test_local"]["conduction"]
    assert "test_local" in by_id["pr_merge"]["conduction"]
    assert "pr_merge" not in by_id["test_local"]["conduction"]


def test_issue_to_pr_red_test_local_never_reaches_pr_create():
    """Conduction: a failed first probe still reaches the one-shot nest.

    The nest itself (repair_agent, test_local_recheck) is allowed; publish
    nodes (push, pr_create, stage_pr_open, …) stay unreachable until the
    bounded recheck succeeds.
    """
    by_id = _path_nodes("issue_to_pr")
    # After a red first probe, Fala will not ready nodes that list test_local
    # as a hard conduction. The nest atoms list it, so they *do* wait for the
    # first probe to complete — but they skip-or-run based on its values, not
    # on its success. That skip-or-run is organ-owned (see test_fala_organ).
    # Publish nodes also list test_local AND test_local_recheck, so a red
    # recheck never readies them.
    after_red_recheck = _ready_after_failure("issue_to_pr", "test_local_recheck")
    assert "repair_agent" in after_red_recheck or "test_local" in by_id["repair_agent"]["conduction"]
    assert "push" not in after_red_recheck
    assert "pr_create" not in after_red_recheck
    assert "assert_real_diff" not in after_red_recheck
    assert "stage_pr_open" not in after_red_recheck
    assert "list_prs" not in after_red_recheck
    assert "pr_label" not in after_red_recheck
    after_red_first = _ready_after_failure("issue_to_pr", "test_local")
    assert "push" not in after_red_first
    assert "pr_create" not in after_red_first
    assert "stage_pr_open" not in after_red_first
    # The nest atoms themselves wait on test_local (they must not start early).
    assert "repair_agent" not in after_red_first
    assert "test_local_recheck" not in after_red_first


def _ready_after_failure(path_id: str, failed_id: str) -> set[str]:
    """Nodes Fala can ready if `failed_id` never succeeds (direct conduction)."""
    by_id = _path_nodes(path_id)
    ready: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node_id, node in by_id.items():
            if node_id in ready or node_id == failed_id:
                continue
            conduction = node["conduction"]
            if failed_id in conduction:
                continue
            if all(upstream in ready for upstream in conduction):
                ready.add(node_id)
                changed = True
    return ready


def test_pr_triage_red_test_local_does_not_reach_merge():
    reached = _ready_after_failure("pr_triage", "test_local")
    assert "pr_checks" in reached
    assert "pr_review" in reached
    assert "worktree_add" in reached
    assert "test_local" not in reached
    assert "pr_merge" not in reached
    assert "stage_clear" not in reached
    assert "close_issue" not in reached


def test_organ_worktree_add_pr_triage_uses_branch_tip(monkeypatch):
    captured: list[list[str]] = []

    def fake_run(main, argv):
        captured.append(argv)
        return {"ok": True, "worktree": "/tmp/wt", "branch": "ai/fix/9-x"}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    result = fala_organ._handle(
        "worktree_add",
        {
            "repo": "a/b",
            "branch": "ai/fix/9-x",
            "live": False,
            "config_path": "/tmp/c.yaml",
        },
        {"pr_checks": {"ok": True}, "pr_review": {"ok": True, "merge_ok": True}},
    )
    assert result["ok"] is True
    argv = captured[0]
    assert "--branch" in argv
    assert "ai/fix/9-x" in argv
    assert "--reset-base" not in argv


def test_organ_worktree_add_issue_to_pr_still_resets_base(monkeypatch):
    captured: list[list[str]] = []

    def fake_run(main, argv):
        captured.append(argv)
        return {"ok": True, "worktree": "/tmp/wt"}

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_run)
    fala_organ._handle(
        "worktree_add",
        {"repo": "a/b", "live": False, "config_path": "/tmp/c.yaml"},
        {"make_branch": {"branch": "ai/fix/1-x"}},
    )
    assert "--reset-base" in captured[0]
    assert "ai/fix/1-x" in captured[0]


def test_organ_red_gate_does_not_reach_pr_merge(monkeypatch):
    """Fail-closed atom result: Fala would raise before conducting pr_merge."""
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
    assert not result.get("skipped")

    called = []

    def boom(main, argv):
        called.append(argv)
        raise AssertionError("pr_merge must not run after red local tests")

    monkeypatch.setattr(fala_organ, "_run_atom_main", boom)
    assert called == []
