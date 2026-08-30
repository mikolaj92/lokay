"""Refuse a product pass when host fast-forward requires a process restart.

Always succeeds. Fala unblocks children of a failed atom, so `ok=false`
cannot stop departments. `route=begin` continues; `route=restart` is
host_updated. Selects skip in Python; factory_begin has `when` begin.
"""

from pathlib import Path
from lokay.git_host_ff import process_head_moved


def gate(host: dict, *, live: bool, checkout: str) -> dict:
    if not live:
        return {"ok": True, "route": "begin"}
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
