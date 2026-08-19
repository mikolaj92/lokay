"""Committed source evidence used by the agent repair lane."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from lokay.organ.common import _localize_paths


def head_has_on_goal_src(worktree: str, localized: dict[str, Any] | None) -> bool:
    """Return true when the issue branch HEAD already committed scoped source."""
    if not isinstance(localized, dict):
        try:
            payload = json.loads(
                (Path(worktree) / ".lokay" / "localize.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError):
            return False
        localized = payload if isinstance(payload, dict) else None
    scopes = _localize_paths({"localize": localized}) if localized else []
    if not scopes:
        return False
    try:
        changed = subprocess.run(
            [
                "git",
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "-r",
                "HEAD",
            ],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return False
    return any(
        path.startswith("src/")
        and any(path == scope or path.startswith(f"{scope}/") for scope in scopes)
        for path in changed
    )
