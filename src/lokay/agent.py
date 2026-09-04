"""Agent slot — run a configured external coding harness.

No stubs. No silent defaults. No per-vendor argv hardcoding in lokay code.
The slot writes an artifact and structured output. It does not persist a
revision; that is a later graph atom after a ready verdict.

Lokay only knows:
  - executor.command  — binary on PATH
  - executor.args     — argv template with placeholders
  - executor.agent    — label for logs/state (any non-stub name)

Switch harness by editing config (command/args), not by forking lokay.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from lokay.config import Config
from lokay.runner import CommandSpec, Runner

STUB_AGENTS = frozenset({"fake", "stub", "mock", "noop"})
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")

# This is an execution boundary, not an intake classifier (#94 owns detection).
# It is appended to every harness prompt so a collector-shaped task cannot turn
# Pi into a long-running data-population worker.
COLLECTOR_BOUNDARY = """
Collector boundary (applies only when the task involves unbounded collection):
- Work only on a bounded collector/bootstrap patch. Its durable background
  startup hook is activated after merge/deployment; do not start a collection
  job from this coding session.
- Pi and Lokay must not populate collection data, poll collection
  progress, or wait for collection completion.
- A later, separate issue evaluates whether the background collector produced
  useful results. Do not claim that result from this task.
""".strip()


def with_collector_boundary(prompt: str) -> str:
    """Attach the collector execution boundary without classifying the task."""
    return f"{(prompt or '').rstrip()}\n\n{COLLECTOR_BOUNDARY}\n"


class AgentError(RuntimeError):
    pass


def resolve_agent_kind(config: Config) -> str:
    """Log label only (not an allowlist). LOKAY_AGENT overrides config.agent."""
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


def session_id_for_worktree(worktree: Path, *, kind: str = "code") -> str:
    """Stable per-corner session so a timeout retry continues, not a new lottery.

    Pair with Pi ``--session-id`` (creates if missing). ``--session`` looks
    up an existing file and exits 1 on the first ticket. Semantic slots
    (intake / queue / localize) use a distinct ``kind`` so they cannot
    resume a coding session or poison its transcript.
    """
    digest = hashlib.sha256(str(Path(worktree).resolve()).encode()).hexdigest()[:16]
    suffix = "" if kind in {"", "code"} else f"-{kind}"
    return f"lokay-{digest}{suffix}"


def _values(
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    command: str,
    session_kind: str = "code",
    timeout_seconds: int | None = None,
) -> dict[str, str]:
    timeout = int(config.timeout_seconds if timeout_seconds is None else timeout_seconds)
    return {
        "command": command,
        "cwd": str(worktree),
        "prompt": prompt,
        "model": (config.agent_model or "").strip(),
        "max_turns": str(int(config.max_turns)),
        "timeout": str(timeout),
        "session": session_id_for_worktree(worktree, kind=session_kind),
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


def build_agent_argv(
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    session_kind: str = "code",
    timeout_seconds: int | None = None,
) -> list[str]:
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
            "({cwd} {prompt} {model} {max_turns} {timeout} {session})"
        )
    values = _values(
        config,
        worktree=worktree,
        prompt=prompt,
        command=command,
        session_kind=session_kind,
        timeout_seconds=timeout_seconds,
    )
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


def run_agent(
    runner: Runner,
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    execute: bool,
    session_kind: str = "code",
    timeout_seconds: int | None = None,
    attach_collector_boundary: bool = True,
) -> dict:
    """Run configured harness. execute=False → plan only."""
    kind = resolve_agent_kind(config)
    effective_prompt = (
        with_collector_boundary(prompt) if attach_collector_boundary else (prompt or "")
    )
    argv = build_agent_argv(
        config,
        worktree=worktree,
        prompt=effective_prompt,
        session_kind=session_kind,
        timeout_seconds=timeout_seconds,
    )
    display = [("<prompt>" if p == effective_prompt else p) for p in argv]

    if not execute:
        return {
            "status": "planned",
            "agent": kind,
            "command": display,
            "prompt_len": len(effective_prompt),
            "collector_boundary": bool(attach_collector_boundary),
            "worktree": str(worktree),
            "executor_enabled": config.executor_enabled,
            "execute": execute,
            "session": session_id_for_worktree(worktree, kind=session_kind),
        }

    if not config.executor_enabled:
        raise AgentError(
            "executor.enabled is false — refuse agent execute "
            "(no silent plan fallback when execute was requested)"
        )

    timeout = int(config.timeout_seconds if timeout_seconds is None else timeout_seconds)
    result = runner.run(
        CommandSpec(
            argv=tuple(argv),
            cwd=str(worktree),
            # Never delegate the orchestration health capability to the coding agent.
            env={"LOKAY_HEALTH_LEASE": ""},
            timeout_seconds=timeout,
        ),
        live=True,
    )
    timed_out = bool(getattr(result, "timed_out", False))
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "agent": kind,
        "returncode": result.returncode,
        "timed_out": timed_out,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
        "collector_boundary": bool(attach_collector_boundary),
        "worktree": str(worktree),
        "session": session_id_for_worktree(worktree, kind=session_kind),
    }
