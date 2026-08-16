"""Pass workspace files under a per-pass directory (conduction carries the path)."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

# Live mill was leaving one factory-pass-* dir per 60s tick (~1k leftovers).
PASS_DIR_KEEP = 8


def make_pass_dir(state_path: Path) -> Path:
    root = Path(state_path).expanduser().resolve().parent
    path = root / f"factory-pass-{os.getpid()}-{secrets.token_hex(6)}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def prune_pass_dirs(
    state_path: Path,
    *,
    keep: int = PASS_DIR_KEEP,
    keep_path: Path | None = None,
) -> int:
    """Drop stale factory-pass-* workspaces beside state.jsonl.

    Conduction carries the current pass_dir. Older directories are leftovers
    from previous ticks, not a second journal.
    """
    root = Path(state_path).expanduser().resolve().parent
    try:
        dirs = [path for path in root.glob("factory-pass-*") if path.is_dir()]
    except OSError:
        return 0
    pinned: Path | None = None
    if keep_path is not None:
        try:
            pinned = Path(keep_path).expanduser().resolve()
        except OSError:
            pinned = Path(keep_path)
    dirs.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    retain = max(1, int(keep))
    removed = 0
    for stale in dirs[retain:]:
        try:
            resolved = stale.resolve()
        except OSError:
            resolved = stale
        if pinned is not None and resolved == pinned:
            continue
        shutil.rmtree(stale, ignore_errors=True)
        removed += 1
    return removed


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
