from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from lokay.safety import SafetyError, validate_argv

# Force machine-readable CLI output. Host shells often export CLICOLOR_FORCE /
# FORCE_COLOR which make modern `gh --json` emit ANSI and break json.loads.
_MACHINE_ENV = {
    "NO_COLOR": "1",
    "CLICOLOR": "0",
    "CLICOLOR_FORCE": "0",
    "FORCE_COLOR": "0",
    "GH_FORCE_TTY": "0",
    "TERM": "dumb",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR/CSI sequences (defensive if a child still colors)."""
    if not text or "\x1b" not in text:
        return text
    return _ANSI_RE.sub("", text)


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
        env.update(_MACHINE_ENV)
        env.update(spec.env)
        # Spec env must not re-enable forced color for machine parsers.
        env["NO_COLOR"] = "1"
        env["CLICOLOR_FORCE"] = "0"
        env["FORCE_COLOR"] = "0"
        env["GH_FORCE_TTY"] = "0"
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
            stdout=strip_ansi(completed.stdout or ""),
            stderr=strip_ansi(completed.stderr or ""),
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError(
                f"command failed ({result.returncode}): {spec.display()}\n"
                f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
            )
        return result
