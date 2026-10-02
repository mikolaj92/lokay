"""Atomic: run the repository-declared local test command in a worktree.

Use the checkout's existing pytest, Swift or Pixi declarations.
An explicit `[tool.lokay] test` overrides those native commands; no declaration
remains an honest skip. There is only one runner.
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
from lokay.test_cache import cache_key, read_green, write_green

TEST_TIMEOUT_SECONDS = 1800
MINI_LOKAY_REPO_SCOPE = "mikolaj92/lokay"


def _argv_from_raw(raw: object, key: str = "test") -> tuple[str, ...] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        argv = tuple(shlex.split(raw))
        return argv or None
    if isinstance(raw, list):
        if not raw:
            return None
        if not all(isinstance(item, str) and item.strip() for item in raw):
            raise ValueError(f"tool.lokay.{key} must be a string or list of strings")
        return tuple(str(item) for item in raw)
    raise ValueError(f"tool.lokay.{key} must be a string or list of strings")


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
        path for path in paths if path.startswith("tests/") and path.endswith(".py")
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


def declared_argv(worktree: Path, key: str) -> tuple[str, ...] | None:
    """Return one repo-declared argv, or None when that key is absent."""
    pyproject = worktree / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot read tool.lokay.{key}: {exc}") from exc
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    lokay = tool.get("lokay")
    if not isinstance(lokay, dict) or key not in lokay:
        return None
    return _argv_from_raw(lokay.get(key), key)


def declared_test_argv(worktree: Path) -> tuple[str, ...] | None:
    """Use native project declarations unless the repo explicitly overrides them."""
    explicit = declared_argv(worktree, "test")
    if explicit:
        return explicit
    commands: list[tuple[str, ...]] = []
    pixi = worktree / "pixi.toml"
    if pixi.is_file():
        tasks = tomllib.loads(pixi.read_text(encoding="utf-8")).get("tasks", {})
        task = next((name for name in ("full-smoke", "test", "core-smoke") if name in tasks), None)
        if task:
            commands.append(("pixi", "run", task))
    if (worktree / "Package.swift").is_file():
        commands.append(("swift", "test"))
    pyproject = worktree / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8")) if pyproject.is_file() else {}
    if "pytest" in data.get("tool", {}):
        dev = ("--group", "dev") if "dev" in data.get("dependency-groups", {}) else (
            ("--extra", "dev") if "dev" in data.get("project", {}).get("optional-dependencies", {}) else ()
        )
        commands.append(("uv", "run", *dev, "pytest", "-q"))
    if not commands:
        return None
    if len(commands) == 1:
        return commands[0]
    return ("sh", "-c", " && ".join(shlex.join(command) for command in commands))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-test-local")
    p.add_argument("--repo", default=MINI_LOKAY_REPO_SCOPE)
    p.add_argument("--worktree", required=True)
    p.add_argument("--changed-scope", action="store_true")
    args = p.parse_args(argv)
    from lokay.proc.test_local_execution_subflow import run

    return emit_exit(
        run(worktree=args.worktree, changed_scope=bool(args.changed_scope))
    )


if __name__ == "__main__":
    raise SystemExit(main())
