"""Resolve the canonical Lokay checkout and recovery worktree paths."""

import argparse
from lokay.proc._common import load_cfg

REPO = "mikolaj92/lokay"


def resolve(*, config_path: str | None, fingerprint: str) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    repo = next((x for x in cfg.active_repos() if x.name == REPO), None)
    if repo is None:
        return {"ok": False, "error": "canonical Lokay checkout unavailable"}
    worktree = cfg.worktrees_root / "_self_repair" / fingerprint
    return {
        "ok": True,
        "repo": REPO,
        "clone": str(repo.clone_path),
        "managed_root": str(cfg.worktrees_root),
        "worktree": str(worktree),
        "fingerprint": fingerprint,
        "exists": worktree.exists(),
    }
