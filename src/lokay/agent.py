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

# Factory owns claim/publish. Product AGENTS.md / CLAUDE.md / docs/agents
# playbooks in the checkout may still tell humans (or other orchestrators) to
# take_issue/gh/PR — this coding slot must ignore those publication rules.
FACTORY_WORKFLOW_BOUNDARY = """
Factory workflow boundary (Lokay coding session — overrides product playbooks):
- This slot is owned by the Lokay factory graph, not by product AGENTS.md,
  CLAUDE.md, or docs/agents GitHub workflow playbooks in the checkout.
- Do NOT run scripts/take_issue.py, claim/assign issues, call `gh`, push,
  open/merge PRs, or close issues — even if a product playbook says tracked
  work requires that.
- Claim/assign, branch, and worktree already happened before this step as
  deterministic atoms. Commit/push/PR happen after as deterministic atoms.
- Your only job: edit files in this worktree and return one closed JSON
  object {verdict, evidence_kind, summary, tests_run, residual_risk}.
  The edited files are the diff, not a JSON key. Architecture notes in
  product docs may still guide *how* to change code; publication/claim steps do not.
""".strip()


def with_collector_boundary(prompt: str) -> str:
    """Attach collector + factory workflow boundaries without classifying the task."""
    return with_coding_boundaries(prompt)


def with_coding_boundaries(prompt: str) -> str:
    """Append fail-closed factory boundaries to a coding harness prompt."""
    return (
        f"{(prompt or '').rstrip()}\n\n"
        f"{COLLECTOR_BOUNDARY}\n\n"
        f"{FACTORY_WORKFLOW_BOUNDARY}\n"
    )


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
    session: str = "",
) -> dict[str, str]:
    timeout = int(config.timeout_seconds if timeout_seconds is None else timeout_seconds)
    return {
        "command": command,
        "cwd": str(worktree),
        "prompt": prompt,
        "max_turns": str(int(config.max_turns)),
        "timeout": str(timeout),
        "session": session or session_id_for_worktree(worktree, kind=session_kind),
    }


def _render_arg(token: str, values: dict[str, str]) -> str:
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
    argv, _ = _build_agent_invocation(
        config, worktree=worktree, prompt=prompt, session_kind=session_kind,
        timeout_seconds=timeout_seconds,
    )
    return argv


def _build_agent_invocation(
    config: Config,
    *,
    worktree: Path,
    prompt: str,
    session_kind: str,
    timeout_seconds: int | None,
    session: str = "",
) -> tuple[list[str], str]:
    """Return argv and the session explicitly bound by the trusted template.

    A worktree-derived retry key alone is not execution evidence. Only a
    {session} placeholder in an argument actually passed to the harness binds
    it; model output and coincidental occurrences in prompt text do not.
    """
    command = (config.agent_command or "").strip()
    if not command:
        raise AgentError(
            "executor.command is empty — set the harness binary"
        )
    raw_args = list(config.agent_args or [])
    if not raw_args:
        raise AgentError(
            "executor.args is empty — set argv template "
            "({cwd} {prompt} {max_turns} {timeout} {session})"
        )
    values = _values(
        config,
        worktree=worktree,
        prompt=prompt,
        command=command,
        session_kind=session_kind,
        timeout_seconds=timeout_seconds,
        session=session,
    )
    argv: list[str] = [command]
    session = ""
    for token in raw_args:
        tok = str(token)
        argv.append(_render_arg(tok, values))
        if "session" in _PLACEHOLDER_RE.findall(tok):
            session = values["session"]
    return argv, session


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
    session_policy: str = "",
    session_role: str = "",
    repo: str = "",
    issue: int | None = None,
    branch: str = "",
    head_sha: str = "",
    base_sha: str = "",
    prior_session: dict | None = None,
) -> dict:
    """Run configured harness. execute=False → plan only."""
    kind = resolve_agent_kind(config)
    effective_prompt = (
        with_collector_boundary(prompt) if attach_collector_boundary else (prompt or "")
    )
    receipt = ""
    bound_session = ""
    if session_policy:
        import json as _json
        from lokay.session_policy import resolve_session

        resolved = resolve_session(
            policy=session_policy, repo=repo, role=session_role or "builder",
            issue=issue, branch=branch, head_sha=head_sha, base_sha=base_sha,
            prior=prior_session,
        )
        bound_session = str(resolved["session_id"])
        receipt = _json.dumps(resolved, sort_keys=True)
    argv, session = _build_agent_invocation(
        config,
        worktree=worktree,
        prompt=effective_prompt,
        session_kind=session_kind,
        timeout_seconds=timeout_seconds,
        session=bound_session,
    )
    harness = list(argv)
    display = [("<prompt>" if p == effective_prompt else p) for p in harness]

    if not execute:
        return {
            "status": "planned",
            "agent": kind,
            "command": display,
            "prompt_len": len(effective_prompt),
            "collector_boundary": bool(attach_collector_boundary),
            "factory_workflow_boundary": bool(attach_collector_boundary),
            "worktree": str(worktree),
            "executor_enabled": config.executor_enabled,
            "execute": execute,
            "session": "",  # A planned invocation is not execution evidence.
        }

    if not config.executor_enabled:
        raise AgentError(
            "executor.enabled is false — refuse agent execute "
            "(no silent plan fallback when execute was requested)"
        )

    timeout = int(config.timeout_seconds if timeout_seconds is None else timeout_seconds)
    role = "reviewer" if str(session_kind).startswith("review") else "builder"
    from lokay.proc.repair_agent_revision import observe

    before = observe(runner, worktree) if session_kind == "code" else {}
    result = runner.run(
        CommandSpec(
            argv=tuple(argv),
            cwd=str(worktree),
            # Inherit the harness runtime unchanged; only Lokay's host lease
            # stays with the orchestrator, never its child process.
            env={"LOKAY_HEALTH_LEASE": ""},
            timeout_seconds=timeout,
        ),
        live=True,
    )
    timed_out = bool(getattr(result, "timed_out", False))
    full_stdout = result.stdout or ""
    out = {
        "revision": {"before": before, "after": observe(runner, worktree)} if before else {},
        "status": "completed" if result.returncode == 0 else "failed",
        "agent": kind,
        "returncode": result.returncode,
        "timed_out": timed_out,
        "stdout_tail": full_stdout[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
        "collector_boundary": bool(attach_collector_boundary),
        "factory_workflow_boundary": bool(attach_collector_boundary),
        "worktree": str(worktree),
        "session": session if getattr(result, "executed", False) else "",
        "session_receipt": receipt if session and getattr(result, "executed", False) else "",
    }
    if role == "builder":
        # The result document rides its own bounded channel; the tail stays
        # diagnostics. Past the bound the outcome is named truncation,
        # never a partial "valid" result.
        limit = 200_000
        if len(full_stdout) > limit:
            out["result_stdout"] = full_stdout[:limit]
            out["result_truncated"] = "result_transport_limit"
        else:
            out["result_stdout"] = full_stdout
    return out
