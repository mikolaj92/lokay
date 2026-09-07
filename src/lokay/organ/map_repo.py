"""Fala binding: inspect the checkout before triage or coding."""

from __future__ import annotations

from typing import Any

from lokay.config import load_config
from lokay.proc._common import resolve_repo_clone


def handle_map_repo(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom != "map_repo":
        return None
    worktree = str(
        (up.get("worktree_add") or {}).get("worktree")
        or inputs.get("worktree")
        or inputs.get("clone_path")
        or ""
    )
    if not worktree:
        try:
            cfg = load_config(str(inputs.get("config_path") or "") or None)
            clone = resolve_repo_clone(cfg, str(ctx.get("repo") or inputs.get("repo") or ""))
        except (KeyError, OSError, TypeError, ValueError):
            clone = None
        worktree = str(clone or "")
    issue = dict((up.get("get_issue") or {}).get("issue") or inputs.get("issue_raw") or {})
    from lokay.proc.map_repo import map_repo

    return map_repo(
        worktree=worktree,
        title=str(issue.get("title") or inputs.get("title") or ""),
        body=str(issue.get("body") or inputs.get("body") or ""),
    )
