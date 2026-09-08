"""Refuse a product pass when host fast-forward requires a process restart.

Always succeeds as a routing atom. Fala unblocks children of failed atoms,
so failure or missing sync evidence selects `blocked`, not `begin`.
`restart` means host_updated. Departments skip both stopped routes;
record_pass persists the gate health before reporting the result.
"""

from pathlib import Path
from lokay.git_host_ff import process_head_moved


def gate(host: dict, *, live: bool, checkout: str) -> dict:
    if not live:
        return {"ok": True, "route": "begin"}
    if host.get("ok") is not True:
        return {
            "ok": True, "route": "blocked", "health": "host_behind",
            "reason": str(host.get("reason") or "host_sync_missing"),
            "error": str(host.get("error") or "host sync did not succeed"),
        }
    if host.get("updated") is True:
        return {
            "ok": True,
            "route": "restart",
            "reason": "host_updated",
            "health": "host_updated",
            "restart_required": True,
            "head": host.get("head"),
            "origin_main": host.get("origin_main"),
        }
    moved = process_head_moved(Path(checkout)) if checkout else None
    if moved is not None:
        return {
            "ok": True,
            "route": "restart",
            "reason": "host_updated",
            "health": "host_updated",
            "restart_required": True,
            "error": moved.get("error"),
            "head": moved.get("head"),
            "origin_main": moved.get("origin_main"),
            "process_head": moved.get("process_head"),
        }
    return {"ok": True, "route": "begin"}
