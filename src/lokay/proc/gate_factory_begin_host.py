"""Refuse a product pass when host fast-forward requires a process restart."""

import os
from pathlib import Path
from lokay.git_host_ff import process_head_moved


def gate(host: dict, *, live: bool, checkout: str) -> dict:
    if live and host.get("updated") is True:
        return {
            "ok": False,
            "error": "host checkout updated; restart required before product work",
            "reason": "host_updated",
            "health": "host_updated",
            "restart_required": True,
            "head": host.get("head"),
            "origin_main": host.get("origin_main"),
        }
    moved = process_head_moved(Path(checkout)) if live and checkout else None
    return moved if moved is not None else {"ok": True, "route": "begin"}
