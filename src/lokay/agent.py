"""Agent slot — the only non-deterministic step. Harness is swappable."""

from __future__ import annotations

import os
from pathlib import Path

from lokay.config import Config
from lokay.runner import CommandSpec, Runner


def build_grok_argv(config: Config, *, worktree: Path, prompt: str) -> list[str]:
    argv: list[str] = [config.grok_command, "--cwd", str(worktree)]
    if config.always_approve:
        argv.append("--always-approve")
    argv.extend(["--max-turns", str(config.max_turns)])
    argv.extend(["--output-format", "plain"])
    if config.grok_model:
        argv.extend(["-m", config.grok_model])
    argv.extend(["--permission-mode", "acceptEdits"])
    argv.append(prompt)
    return argv


def run_fake_agent(*, worktree: Path, prompt: str) -> dict:
    """Deterministic stand-in for CI/canary: apply a trivial fix marker."""
    marker = worktree / "LOKAY_CANARY.md"
    marker.write_text(
        "# Lokay canary\n\nAgent slot ran (fake).\n\nPrompt bytes: "
        f"{len(prompt)}\n",
        encoding="utf-8",
    )
    # optional: touch a known broken file pattern from canary issues
    todo = worktree / "CANARY_TODO.txt"
    if todo.is_file() and "FIXME" in todo.read_text(encoding="utf-8"):
        todo.write_text("fixed by lokay fake agent\n", encoding="utf-8")
    return {
        "status": "completed",
        "agent": "fake",
        "worktree": str(worktree),
        "files": ["LOKAY_CANARY.md"] + (["CANARY_TODO.txt"] if todo.is_file() else []),
        "stdout_tail": "fake agent wrote LOKAY_CANARY.md",
    }


def run_agent(
    runner: Runner,
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    execute: bool,
) -> dict:
    """Run the configured agent.

    execute=False → plan only (no process).
    Agent kind: config.agent or env LOKAY_AGENT (fake|grok).
    """
    kind = (os.environ.get("LOKAY_AGENT") or config.agent or "grok").strip().lower()
    if not execute or not config.executor_enabled:
        argv = (
            ["fake-agent", str(worktree)]
            if kind == "fake"
            else build_grok_argv(config, worktree=worktree, prompt=prompt)[:-1] + ["<prompt>"]
        )
        return {
            "status": "planned",
            "agent": kind,
            "command": argv,
            "prompt_len": len(prompt),
            "worktree": str(worktree),
            "executor_enabled": config.executor_enabled,
            "execute": execute,
        }

    if kind == "fake":
        return run_fake_agent(worktree=worktree, prompt=prompt)

    argv = build_grok_argv(config, worktree=worktree, prompt=prompt)
    spec = CommandSpec(
        argv=tuple(argv),
        cwd=str(worktree),
        timeout_seconds=config.timeout_seconds,
    )
    result = runner.run(spec, live=True)
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "agent": "grok",
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
        "worktree": str(worktree),
    }
