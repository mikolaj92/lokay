"""Apply one mutation gate to an issue approach write."""

import argparse
from pathlib import Path

from lokay.proc._common import load_cfg, mutations_allowed


def authorize(request: dict, approach: dict, *, config_path: str | None, live: bool) -> dict:
    if approach.get("ok") is False:
        return {
            "ok": True,
            "route": "terminal",
            "reason": str(approach.get("reason") or "plan_incomplete"),
            "live": False,
        }
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live)) if live else None
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    if allowed and not Path(request["worktree"]).is_dir():
        return {
            "ok": True,
            "route": "terminal",
            "reason": "worktree_missing",
            "live": allowed,
        }
    return {"ok": True, "route": "write" if allowed else "planned", "live": allowed}
