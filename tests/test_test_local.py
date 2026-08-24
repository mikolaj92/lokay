"""Contracts for minimal authored local-test execution atoms."""

from pathlib import Path
from lokay.proc import test_local


def test_this_repo_declares_pytest():
    assert test_local.declared_test_argv(Path(__file__).resolve().parents[1]) == (
        "uv",
        "run",
        "--extra",
        "dev",
        "pytest",
        "-q",
    )


def test_no_declaration_is_closed_skip(tmp_path):
    from lokay.proc.inspect_test_declaration import inspect

    out = inspect(worktree=str(tmp_path))
    assert out["route"] == "terminal" and out["result"]["reason"] == "no_declared_test"


def test_invalid_declaration_fails_closed(tmp_path):
    from lokay.proc.inspect_test_declaration import inspect

    (tmp_path / "pyproject.toml").write_text("[tool.lokay]\ntest=12\n")
    out = inspect(worktree=str(tmp_path))
    assert (
        out["result"]["ok"] is False
        and out["result"]["reason"] == "invalid_test_declaration"
    )


def test_missing_worktree_fails_closed(tmp_path):
    from lokay.proc.inspect_test_declaration import inspect

    assert inspect(worktree=str(tmp_path / "none"))["result"]["ok"] is False


def test_full_green_routes_to_cache():
    from lokay.proc.select_declared_test_outcome import select

    assert select({"route": "green"}, changed_scope=True)["route"] == "cache"


def test_red_full_routes_to_one_scope_when_requested():
    from lokay.proc.select_declared_test_outcome import select

    assert (
        select({"route": "red"}, changed_scope=True)["route"] == "scope"
        and select({"route": "red"}, changed_scope=False)["route"] == "terminal"
    )


def test_green_selection_prefers_scoped():
    from lokay.proc.select_green_test_result import select

    out = select(
        {"route": "green", "tests": "full"}, {"route": "green", "tests": "scoped"}
    )
    assert out["source"]["tests"] == "scoped"


def test_terminal_preserves_red_failure():
    from lokay.proc.build_test_terminal import red

    inspected = {"route": "test", "worktree": "/w", "test_argv": ["true"]}
    out = red(inspected, {"route": "red", "returncode": 1, "tests": "true"}, {})
    assert out["result"]["ok"] is False and out["result"]["returncode"] == 1
