"""Fala bindings for one stale-implementing catalog atom (no 30-slot unroll)."""

from typing import Any


def handle_stale_implementing(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "") or None
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_stale_implementing_reap":
        from lokay.proc.prepare_stale_implementing_reap import prepare
        from lokay.proc.stale_implementing_catalog import REPO_SLOTS

        return prepare(pass_dir=pass_dir, config_path=config, slot_count=REPO_SLOTS)
    if atom == "stale_implementing_catalog":
        from lokay.proc.stale_implementing_catalog import run

        return run(
            up.get("prepare_stale_implementing_reap") or {},
            config_path=config,
            live=live,
        )
    if atom == "persist_stale_implementing_reap":
        from lokay.proc.persist_stale_implementing_reap import persist

        return persist(up.get("stale_implementing_catalog") or {})
    if atom == "summarize_stale_implementing_reap":
        from lokay.proc.summarize_stale_implementing_reap import summarize

        return summarize(
            up.get("prepare_stale_implementing_reap") or {},
            up.get("persist_stale_implementing_reap") or {},
        )
    return None
