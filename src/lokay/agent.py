"""Agent slot — run a configured external coding harness.

No stubs. No silent defaults. No per-vendor argv hardcoding in mill code.

Mill only knows:
  - executor.command  — binary on PATH
  - executor.args     — argv template with placeholders
  - executor.agent    — label for logs/state (any non-stub name)

Switch harness by editing config (command/args), not by forking lokay.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from lokay.config import Config
from lokay.runner import CommandSpec, Runner

STUB_AGENTS = frozenset({"fake", "stub", "mock", "noop"})
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


class AgentError(RuntimeError):
    pass


def resolve_agent_kind(config: Config) -> str:
    """Label only. LOKAY_AGENT overrides config.agent. Never invents a name."""
    env_raw = os.environ.get("LOKAY_AGENT")
    if env_raw is not None and str(env_raw).strip():
        kind = str(env_raw).strip().lower()
    else:
        kind = (config.agent or "").strip().lower()
    if not kind:
        raise AgentError(
            "agent not configured — set executor.agent or LOKAY_AGENT"
        )
    if kind in STUB_AGENTS:
        raise AgentError(
            f"agent={kind!r} is forbidden — no stubs; set a real harness label"
        )
    return kind


def _values(
    config: Config, *, worktree: Path, prompt: str, command: str
) -> dict[str, str]:
    return {
        "command": command,
        "cwd": str(worktree),
        "prompt": prompt,
        "model": (config.agent_model or "").strip(),
        "max_turns": str(int(config.max_turns)),
        "timeout": str(int(config.timeout_seconds)),
    }


def _render_arg(token: str, values: dict[str, str]) -> str | None:
    # Drop optional model flag pair handled by caller; drop bare {model} if empty.
    if token == "{model}" and not values.get("model"):
        return None

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise AgentError(
                f"unknown placeholder {{{key}}} in executor.args "
                f"(allowed: {sorted(values)})"
            )
        return values[key]

    return _PLACEHOLDER_RE.sub(repl, token)


def build_agent_argv(config: Config, *, worktree: Path, prompt: str) -> list[str]:
    """Build argv from executor.command + executor.args. Fail closed on empty."""
    command = (config.agent_command or "").strip()
    if not command:
        raise AgentError(
            "executor.command is empty — set the harness binary"
        )
    raw_args = list(config.agent_args or [])
    if not raw_args:
        raise AgentError(
            "executor.args is empty — set argv template "
            "({cwd} {prompt} {model} {max_turns} {timeout})"
        )
    values = _values(config, worktree=worktree, prompt=prompt, command=command)
    argv: list[str] = [command]
    i = 0
    tokens = [str(t) for t in raw_args]
    while i < len(tokens):
        tok = tokens[i]
        # If a flag is followed by {model} and model is empty, drop both.
        if (
            i + 1 < len(tokens)
            and tokens[i + 1] == "{model}"
            and not values.get("model")
            and tok.startswith("-")
        ):
            i += 2
            continue
        rendered = _render_arg(tok, values)
        if rendered is None:
            i += 1
            continue
        argv.append(rendered)
        i += 1
    return argv


# Thin alias for older imports/tests.
def build_grok_argv(config: Config, *, worktree: Path, prompt: str) -> list[str]:
    return build_agent_argv(config, worktree=worktree, prompt=prompt)


def run_agent(
    runner: Runner,
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    execute: bool,
) -> dict:
    """Run configured harness. execute=False → plan only."""
    kind = resolve_agent_kind(config)
    argv = build_agent_argv(config, worktree=worktree, prompt=prompt)
    display = [("<prompt>" if p == prompt else p) for p in argv]

    if not execute:
        return {
            "status": "planned",
            "agent": kind,
            "command": display,
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

    result = runner.run(
        CommandSpec(
            argv=tuple(argv),
            cwd=str(worktree),
            timeout_seconds=config.timeout_seconds,
        ),
        live=True,
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "agent": kind,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
        "worktree": str(worktree),
    }
