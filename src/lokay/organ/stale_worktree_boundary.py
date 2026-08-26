"""Fala bindings for one stale-worktree catalog atom (no 4-slot unroll)."""

from typing import Any


def handle_stale_worktree(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "collect_stale_worktree_candidates":
        from lokay.proc.collect_stale_worktree_candidates import collect

        return collect(pass_dir=pass_dir, config_path=config)
    if atom == "stale_worktree_catalog":
        from lokay.proc.stale_worktree_catalog import run

        return run(
            up.get("collect_stale_worktree_candidates") or {},
            config_path=config,
            live=live,
        )
    if atom == "summarize_stale_worktree_reap":
        from lokay.proc.summarize_stale_worktree_reap import summarize

        catalog = up.get("stale_worktree_catalog") or {}
        return summarize(
            pass_dir=pass_dir,
            collected=up.get("collect_stale_worktree_candidates") or {},
            effects=list(catalog.get("effects") or []),
            live=live,
        )
    return None
