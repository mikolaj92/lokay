"""Pass workspace files under a per-pass directory (conduction carries the path)."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


def make_pass_dir(state_path: Path) -> Path:
    root = Path(state_path).expanduser().resolve().parent
    path = root / f"factory-pass-{os.getpid()}-{secrets.token_hex(6)}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


def begin_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "begin.json"


def survey_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "survey.json"


def plan_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "plan.json"


def working_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "working.json"


def implement_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "implement.json"


def tick_path(pass_dir: Path | str) -> Path:
    return Path(pass_dir) / "tick.json"
