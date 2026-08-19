"""Atomic: run the repository-declared local test command in a worktree.

Verification is declared by the checkout (`[tool.lokay] test` in
``pyproject.toml``), not inferred from ``pyproject`` / ``tests/``. Missing
declaration is an honest skip — do not invent ``uv run --extra dev pytest``.
"""

from __future__ import annotations

import argparse
import shlex
import tomllib
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import list_changed_paths
from lokay.proc._common import runner
from lokay.runner import CommandSpec, Runner

TEST_TIMEOUT_SECONDS = 1800
MINI_MILL_REPO = "mikolaj92/lokay"


def _argv_from_raw(raw: object) -> tuple[str, ...] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        argv = tuple(shlex.split(raw))
        return argv or None
    if isinstance(raw, list):
        if not raw:
            return None
        if not all(isinstance(item, str) and item.strip() for item in raw):
            raise ValueError("tool.lokay.test must be a string or list of strings")
        return tuple(str(item) for item in raw)
    raise ValueError("tool.lokay.test must be a string or list of strings")


def _changed_pytest_argv(
    run: Runner, worktree: Path, test_argv: tuple[str, ...]
) -> tuple[str, ...] | None:
    """Narrow pytest to tests covering changed source; fail closed if unknown."""
    if not any(Path(part).name in {"pytest", "py.test"} for part in test_argv):
        return None
    paths = list_changed_paths(run, worktree, base="origin/main")
    source_stems = {
        Path(path).stem
        for path in paths
        if path.startswith("src/") and path.endswith(".py")
    }
    if not source_stems:
        return None
    tests = {
        path
        for path in paths
        if path.startswith("tests/") and path.endswith(".py")
    }
    test_root = worktree / "tests"
    if test_root.is_dir():
        for stem in source_stems:
            tests.update(
                path.relative_to(worktree).as_posix()
                for path in test_root.rglob(f"test_{stem}.py")
            )
    if not tests:
        return None
    return (*test_argv, *sorted(tests))


def declared_test_argv(worktree: Path) -> tuple[str, ...] | None:
    """Return the repo-declared test argv, or None when none is declared."""
    pyproject = worktree / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot read tool.lokay.test: {exc}") from exc
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    lokay = tool.get("lokay")
    if not isinstance(lokay, dict):
        return None
    return _argv_from_raw(lokay.get("test"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-test-local")
    p.add_argument("--repo", default=MINI_MILL_REPO)
    p.add_argument("--worktree", required=True)
    p.add_argument(
        "--changed-scope",
        action="store_true",
        help="if the full pytest suite is red, verify tests covering changed src",
    )
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                tested=False,
                repo=args.repo,
                worktree=args.worktree,
            )
        )
    worktree = Path(args.worktree).resolve()
    if not worktree.is_dir():
        return emit_exit(err("worktree is not a directory", worktree=str(worktree)))
    try:
        test_argv = declared_test_argv(worktree)
    except ValueError as exc:
        return emit_exit(
            err(
                str(exc),
                reason="invalid_test_declaration",
                tested=False,
                worktree=str(worktree),
            )
        )
    if not test_argv:
        return emit_exit(
            ok(
                skipped=True,
                reason="no_declared_test",
                tested=False,
                worktree=str(worktree),
            )
        )
    run = runner()
    try:
        tests = run.run(
            CommandSpec(
                test_argv,
                cwd=str(worktree),
                # Verifier is not a mill atom — do not inherit the capability.
                env={
                    "LOKAY_HEALTH_LEASE": "",
                    "LOKAY_HEALTH_LEASE_PATH": "",
                },
                timeout_seconds=TEST_TIMEOUT_SECONDS,
            ),
            live=True,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), worktree=str(worktree)))
    command = " ".join(test_argv)
    if tests.returncode != 0 and args.changed_scope:
        try:
            scoped_argv = _changed_pytest_argv(run, worktree, test_argv)
            if scoped_argv is not None:
                scoped = run.run(
                    CommandSpec(
                        scoped_argv,
                        cwd=str(worktree),
                        env={
                            "LOKAY_HEALTH_LEASE": "",
                            "LOKAY_HEALTH_LEASE_PATH": "",
                        },
                        timeout_seconds=TEST_TIMEOUT_SECONDS,
                    ),
                    live=True,
                )
                if scoped.returncode == 0:
                    return emit_exit(
                        ok(
                            skipped=False,
                            tested=True,
                            scoped=True,
                            full_suite_returncode=tests.returncode,
                            worktree=str(worktree),
                            tests=" ".join(scoped_argv),
                        )
                    )
                tests = scoped
                command = " ".join(scoped_argv)
        except Exception as exc:  # noqa: BLE001
            return emit_exit(err(str(exc), worktree=str(worktree)))
    if tests.returncode != 0:
        # Bounded failure log for the one-shot repair patch nest (AlphaCodium:
        # the test log drives exactly one repair attempt, never a PR).
        return emit_exit(
            err(
                "local test suite failed",
                returncode=tests.returncode,
                worktree=str(worktree),
                tests=command,
                stdout_tail=(tests.stdout or "")[-4000:],
                stderr_tail=(tests.stderr or "")[-2000:],
            )
        )
    return emit_exit(
        ok(
            skipped=False,
            tested=True,
            worktree=str(worktree),
            tests=command,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
