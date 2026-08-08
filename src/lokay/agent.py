"""Agent slot — real coding harness only. No stubs, no silent fallbacks."""

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

    Fail-closed: empty ``executor.command`` is an error (no invented binary).
    Model is optional: when unset, omit ``-m`` so the CLI uses its own default
    (never substitute another model name here).
    """
    command = (config.grok_command or "").strip()
    if not command:
        raise AgentError(
            "executor.command is empty — set a real harness binary (e.g. grok)"
        )
    argv: list[str] = [command, "--cwd", str(worktree)]
    if config.always_approve:
        argv.append("--always-approve")
    argv.extend(["--max-turns", str(config.max_turns)])
    argv.extend(["--output-format", "plain"])
    if config.grok_model:
        argv.extend(["-m", config.grok_model])
    # Headless tool writes need bypassPermissions; acceptEdits cancels write tools.
    argv.extend(["--permission-mode", "bypassPermissions"])
    # Headless multi-turn with tools (NOT interactive TUI).
    argv.extend(["-p", prompt])
    return argv


def resolve_agent_kind(config: Config) -> str:
    """Resolve harness name. Explicit config/env only — never invent a default.

    Order: non-empty ``LOKAY_AGENT`` env, else ``config.agent``. Empty after
    strip fails closed (no silent ``or "grok"``).
    """
    env_raw = os.environ.get("LOKAY_AGENT")
    if env_raw is not None and str(env_raw).strip():
        kind = str(env_raw).strip().lower()
    else:
        kind = (config.agent or "").strip().lower()
    if not kind:
        raise AgentError(
            "agent not configured — set executor.agent or LOKAY_AGENT "
            "(real harness only; no silent default)"
        )
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
    """Run the real coding agent (grok). Never a stub.

    execute=False → plan only (status planned). execute=True with
    executor.enabled=false fails closed (no silent plan-as-success).
    """
    kind = resolve_agent_kind(config)
    argv = build_grok_argv(config, worktree=worktree, prompt=prompt)

    if not execute:
        return {
            "status": "planned",
            "agent": kind,
            "command": argv[:-1] + ["<prompt>"],
            "prompt_len": len(prompt),
            "worktree": str(worktree),
            "executor_enabled": config.executor_enabled,
            "execute": execute,
        }

    if not config.executor_enabled:
        raise AgentError(
            "executor.enabled is false — refuse agent execute "
            "(no silent plan fallback when execute was requested)"
        )

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
