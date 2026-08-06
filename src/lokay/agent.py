"""Agent slot — real coding harness only. No stubs."""

from __future__ import annotations

import os
from pathlib import Path

from lokay.config import Config
from lokay.runner import CommandSpec, Runner


class AgentError(RuntimeError):
    pass


def build_grok_argv(config: Config, *, worktree: Path, prompt: str) -> list[str]:
    """Build headless grok argv (tools + multi-turn).

    Positional prompt starts the interactive TUI and fails without a TTY
    ("Device not configured"). Headless mode is ``-p/--single`` (or
    ``--prompt-file``) with ``--output-format`` — see grok README Headless Mode.
    """
    argv: list[str] = [config.grok_command, "--cwd", str(worktree)]
    if config.always_approve:
        argv.append("--always-approve")
    argv.extend(["--max-turns", str(config.max_turns)])
    argv.extend(["--output-format", "plain"])
    if config.grok_model:
        argv.extend(["-m", config.grok_model])
    # acceptEdits + always-approve is enough for factory writes; bypass is broader.
    argv.extend(["--permission-mode", "acceptEdits"])
    # Headless multi-turn with tools (NOT interactive TUI).
    argv.extend(["-p", prompt])
    return argv


def resolve_agent_kind(config: Config) -> str:
    kind = (os.environ.get("LOKAY_AGENT") or config.agent or "grok").strip().lower()
    if kind in {"fake", "stub", "mock", "noop"}:
        raise AgentError(
            f"agent={kind!r} is forbidden — no stubs; use a real harness (grok)"
        )
    if kind != "grok":
        # future: other real harnesses; reject unknowns for now
        raise AgentError(f"unknown agent {kind!r}; supported real harness: grok")
    return kind


def run_agent(
    runner: Runner,
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    execute: bool,
) -> dict:
    """Run the real coding agent (grok). Never a stub."""
    kind = resolve_agent_kind(config)
    argv = build_grok_argv(config, worktree=worktree, prompt=prompt)

    if not execute or not config.executor_enabled:
        return {
            "status": "planned",
            "agent": kind,
            "command": argv[:-1] + ["<prompt>"],
            "prompt_len": len(prompt),
            "worktree": str(worktree),
            "executor_enabled": config.executor_enabled,
            "execute": execute,
        }

    spec = CommandSpec(
        argv=tuple(argv),
        cwd=str(worktree),
        timeout_seconds=config.timeout_seconds,
    )
    result = runner.run(spec, live=True)
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "agent": kind,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
        "worktree": str(worktree),
    }
