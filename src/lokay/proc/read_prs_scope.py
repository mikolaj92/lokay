"""Read mill PR scope: active repos and branch prefix. No GitHub."""

from __future__ import annotations

import argparse

from lokay.proc._common import load_cfg


def read(*, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    prefix = str(cfg.branch_prefix or "ai/fix").rstrip("/") + "/"
    return {
        "ok": True,
        "repos": [repo.name for repo in cfg.active_repos()],
        "prefix": prefix,
    }
