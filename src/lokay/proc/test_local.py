"""Atomic: run local pytest in a worktree when a Python suite is present."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import runner
from lokay.runner import CommandSpec

TEST_ARGV = ("uv", "run", "--extra", "dev", "pytest", "-q")
TEST_TIMEOUT_SECONDS = 1800


def has_python_test_suite(worktree: Path) -> bool:
    return (worktree / "pyproject.toml").is_file() or (worktree / "tests").is_dir()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-test-local")
    p.add_argument("--worktree", required=True)
    args = p.parse_args(argv)
    worktree = Path(args.worktree).resolve()
    if not worktree.is_dir():
        return emit_exit(err("worktree is not a directory", worktree=str(worktree)))
    if not has_python_test_suite(worktree):
        return emit_exit(
            ok(
                skipped=True,
                reason="no_python_test_suite",
                tested=False,
                worktree=str(worktree),
            )
        )
    try:
        tests = runner().run(
            CommandSpec(
                TEST_ARGV,
                cwd=str(worktree),
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            ),
            live=True,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), worktree=str(worktree)))
    if tests.returncode != 0:
        return emit_exit(
            err(
                "local test suite failed",
                returncode=tests.returncode,
                worktree=str(worktree),
            )
        )
    return emit_exit(
        ok(
            skipped=False,
            tested=True,
            worktree=str(worktree),
            tests="uv run --extra dev pytest -q",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
