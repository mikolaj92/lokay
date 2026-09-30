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


def test_declared_test_command_does_not_inherit_fala_or_secret_environment(
    tmp_path, monkeypatch
):
    import json
    import sys
    from lokay.proc.run_declared_test_command import run

    monkeypatch.setenv("FALA_EFFECTOR_INPUT_DIR", "/private/fala/input")
    monkeypatch.setenv("FALA_EFFECTOR_OUTPUT_DIR", "/private/fala/output")
    monkeypatch.setenv("FALA_EFFECTOR_MANIFEST", "/private/fala/manifest.json")
    monkeypatch.setenv("GH_TOKEN", "must-not-reach-tests")
    script = "import json, os; print(json.dumps(sorted(os.environ)))"

    result = run(
        {"worktree": str(tmp_path)},
        [sys.executable, "-c", script],
    )

    assert result["route"] == "green", result
    child_env = set(json.loads(result["stdout_tail"]))
    assert not any(name.startswith("FALA_EFFECTOR_") for name in child_env)
    assert "GH_TOKEN" not in child_env
    assert {"PATH", "HOME"} <= child_env


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


def test_missing_verify_is_honest_skip(tmp_path):
    from lokay.proc.inspect_verify_declaration import inspect

    (tmp_path / "pyproject.toml").write_text(
        '[tool.lokay]\ntest = ["true"]\n', encoding="utf-8"
    )
    out = inspect(worktree=str(tmp_path))
    assert out["route"] == "terminal"
    assert out["result"]["skipped"] is True
    assert out["result"]["reason"] == "no_declared_verify"


def test_declared_verify_is_a_command_not_a_harness(tmp_path):
    from lokay.proc.inspect_verify_declaration import inspect

    (tmp_path / "pyproject.toml").write_text(
        '[tool.lokay]\nverify = ["uv", "run", "verify-app"]\n', encoding="utf-8"
    )
    out = inspect(worktree=str(tmp_path))
    assert out["route"] == "verify"
    assert out["verify_argv"] == ["uv", "run", "verify-app"]


def test_invalid_verify_fails_closed(tmp_path):
    from lokay.proc.inspect_verify_declaration import inspect

    (tmp_path / "pyproject.toml").write_text("[tool.lokay]\nverify = 12\n")
    out = inspect(worktree=str(tmp_path))
    assert out["route"] == "terminal"
    assert out["result"]["ok"] is False
    assert out["result"]["reason"] == "invalid_verify_declaration"


def test_green_declared_verify_is_product_proof():
    from lokay.proc.run_declared_verify import run

    out = run(
        {"route": "verify", "worktree": "/w", "verify_argv": ["true"]},
        {"route": "green", "returncode": 0, "tests": "true"},
    )
    assert out["ok"] is True and out["verified"] is True and out["skipped"] is False


def test_skipped_verify_is_not_product_proof():
    from lokay.proc.run_declared_verify import run

    out = run(
        {"route": "terminal", "result": {"skipped": True, "reason": "no_declared_verify"}},
        {"route": "green"},
    )
    assert out["verified"] is False and out["reason"] == "no_declared_verify"
