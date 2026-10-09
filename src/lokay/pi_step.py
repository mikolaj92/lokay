from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from lokay.run import run_process


def pi_step(
    prompt: str,
    artifact: Path,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 3600,
) -> dict[str, str]:
    child = dict(os.environ if env is None else env)
    provider = child.get("LOKAY2_PROVIDER", "")
    model = child.get("LOKAY2_MODEL", "")
    if not provider or not model:
        return {"result": "failed", "artifact": ""}
    proc = run_process(
        ["pi", "-p", "--mode", "json", "--provider", provider, "--model", model, prompt],
        cwd=cwd,
        env=child,
        timeout=timeout,
    )
    if proc.returncode != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": str(artifact)}


def emit(payload: dict[str, str]) -> None:
    if payload.get("result") not in ("done", "failed"):
        raise SystemExit(1)
    print(json.dumps(payload, separators=(",", ":")))
