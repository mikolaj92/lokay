from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from lokay.safety import SafetyError, validate_argv


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120

    def display(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class CommandResult:
    spec: CommandSpec
    executed: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""


def git_spec(args: Sequence[str], cwd: str | Path | None = None, timeout_seconds: int = 120) -> CommandSpec:
    return CommandSpec(
        argv=("git", *tuple(args)),
        cwd=str(cwd) if cwd else None,
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout_seconds=timeout_seconds,
    )


def gh_spec(args: Sequence[str], timeout_seconds: int = 120) -> CommandSpec:
    return CommandSpec(argv=("gh", *tuple(args)), timeout_seconds=timeout_seconds)


class Runner:
    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        validate_argv(spec.argv)
        if not live:
            return CommandResult(spec=spec, executed=False, returncode=0)
        env = os.environ.copy()
        env.update(spec.env)
        completed = subprocess.run(
            list(spec.argv),
            cwd=spec.cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
            check=False,
        )
        return CommandResult(
            spec=spec,
            executed=True,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError(
                f"command failed ({result.returncode}): {spec.display()}\n"
                f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
            )
        return result
