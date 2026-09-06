"""Keep the actual local test outcome in recovery evidence."""

from lokay.proc.run_self_repair_tests import run_tests


def test_failed_real_suite_keeps_exit_code(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "recovery-evidence-test"\nversion = "0.0.0"\n'
        'requires-python = ">=3.12"\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8.0"]\n'
    )
    (tmp_path / "test_failure.py").write_text(
        'def test_failure():\n    assert 1 == 2\n'
    )
    result = run_tests({"worktree": str(tmp_path)})
    assert result["ok"] is False
    assert result["test_returncode"] == 1
    assert result["test_timed_out"] is False
