from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from lokay.run import pi_argv, pi_env, run_process, sandboxed


def pi_step(
    prompt: str,
    artifact: Path,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 3600,
    pi_idle_retry: bool = True,
) -> dict[str, str]:
    worktree = cwd if cwd is not None else Path.cwd()
    child = pi_env(os.environ if env is None else env, worktree)
    provider = child.get("LOKAY2_PROVIDER", "")
    model = child.get("LOKAY2_MODEL", "")
    if not provider or not model:
        return {"result": "failed", "artifact": ""}
    proc = run_process(
        sandboxed(pi_argv(prompt, child, json_mode=True), worktree, child),
        cwd=cwd,
        env=child,
        timeout=timeout,
        pi_idle_retry=pi_idle_retry,
    )
    if proc.returncode != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": str(artifact)}


def emit(payload: dict[str, str]) -> None:
    if payload.get("result") not in ("done", "failed"):
        raise SystemExit(1)
    print(json.dumps(payload, separators=(",", ":")))
