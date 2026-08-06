"""Atomic: run the agent slot (fake|grok) in a worktree. Only non-deterministic step."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.agent import run_agent
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

    result = run_agent(
        runner(),
        cfg,
        worktree=Path(args.worktree),
        prompt=prompt,
        execute=execute,
    )
    if args.live and not cfg.executor_enabled:
        result = {**result, "status": "planned", "note": "executor.enabled is false"}
    if args.live and cfg.mode != "live":
        result = {**result, "status": "planned", "note": "config mode is not live"}
    ok_flag = result.get("status") != "failed"
    return emit_exit(ok(**result) if ok_flag else err("agent failed", **result))


if __name__ == "__main__":
    raise SystemExit(main())
