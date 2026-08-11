"""Atomic: validate the recovery candidate before it may reach main."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import runner
from lokay.runner import CommandSpec, git_spec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-validate")
    p.add_argument("--worktree", required=True)
    args = p.parse_args(argv)
    worktree = Path(args.worktree).resolve()
    run = runner()
    try:
        changed = run.run_checked(
            git_spec(["status", "--porcelain"], cwd=worktree), live=True
        ).stdout.strip()
        if not changed:
            raise RuntimeError("self-repair produced zero diff")
        tests = run.run(
            CommandSpec(
                ("uv", "run", "--extra", "dev", "pytest", "-q"),
                cwd=str(worktree),
                timeout_seconds=1800,
            ),
            live=True,
        )
        if tests.returncode != 0:
            raise RuntimeError("self-repair validation suite failed")
        diff = run.run(
            git_spec(["diff", "--check"], cwd=worktree, timeout_seconds=120),
            live=True,
        )
        if diff.returncode != 0:
            raise RuntimeError("self-repair diff check failed")
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(validated=True, worktree=str(worktree), tests="uv run --extra dev pytest -q"))


if __name__ == "__main__":
    raise SystemExit(main())
