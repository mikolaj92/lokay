"""Resolve canonical checkout and mutation authorization for one recovery commit."""

import argparse

from lokay.proc._common import load_cfg, mutations_allowed

REPO = "mikolaj92/lokay"


def prepare(*, config_path: str | None, live: bool, commit: str) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    repo = next((r for r in cfg.active_repos() if r.name == REPO), None)
    if repo is None:
        return {
            "ok": True,
            "route": "terminal",
            "reason": "checkout_unavailable",
            "commit": commit,
        }
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    return {
        "ok": True,
        "route": "status" if allowed else "planned",
        "commit": commit,
        "path": str(repo.clone_path),
        "planned": not allowed,
    }
