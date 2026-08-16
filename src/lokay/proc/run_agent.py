"""Atomic: run configured coding harness in a worktree. Only non-deterministic step."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.agent import AgentError, run_agent
from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.proc._common import add_config_live, agent_execute_allowed, load_cfg, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-run-agent")
    add_config_live(p)
    p.add_argument("--worktree", required=True)
    p.add_argument("--prompt-file")
    p.add_argument("--prompt", default="")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    execute = agent_execute_allowed(cfg, live_flag=args.live)

    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt:
        stdin = read_stdin_json()
        if isinstance(stdin, dict):
            prompt = str(stdin.get("prompt") or "")
    if not prompt:
        return emit_exit(err("missing prompt"))

    # --live without permission to execute is misconfig, not synthetic success.
    if args.live and not execute:
        reasons: list[str] = []
        if not cfg.executor_enabled:
            reasons.append("executor.enabled is false")
        if cfg.mode != "live":
            reasons.append(f"config mode is {cfg.mode!r} (need live)")
        return emit_exit(
            err(
                "refusing --live agent run: "
                + ("; ".join(reasons) or "execute not allowed"),
                status="refused",
                executor_enabled=cfg.executor_enabled,
                mode=cfg.mode,
                live=True,
            )
        )

    try:
        result = run_agent(
            runner(),
            cfg,
            worktree=Path(args.worktree),
            prompt=prompt,
            execute=execute,
        )
    except AgentError as exc:
        return emit_exit(err(str(exc), status="refused"))

    if result.get("timed_out"):
        # Incomplete, not a graph hard-fail: commit leftover work and let
        # repair_agent resume the same corner / session (K=1).
        payload = {**result, "status": "timeout", "reason": "timeout"}
        return emit_exit(ok(**payload))
    if result.get("status") == "failed":
        return emit_exit(err("agent failed", reason="agent_failed", **result))
    return emit_exit(ok(**result))


if __name__ == "__main__":
    raise SystemExit(main())
