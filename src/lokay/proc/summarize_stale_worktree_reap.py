"""Persist the stale-worktree child result and prune expired archives."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc._common import load_cfg
from lokay.proc.prune_preserved_worktree_archives import prune


def _archive_gc(*, config_path: str | None, live: bool) -> dict:
    """One job: TTL GC of `.lokay-preserved` under the configured worktrees root."""
    cfg = load_cfg(argparse.Namespace(config=config_path))
    root = Path(cfg.worktrees_root).expanduser()
    return prune(managed_root=root, live=live)


def persist_result(
    *,
    pass_dir: str,
    collected: dict,
    catalog: dict,
    live: bool,
    config_path: str | None = None,
) -> dict:
    """One job: write keep/remove rows into the pass working ledger, then TTL GC."""
    effects = list(catalog.get("effects") or [])
    rows = [dict(x.get("row") or {}) for x in effects if x.get("row")]
    kept = [x for x in rows if x.get("kept")]
    reaped = [x for x in rows if x.get("removed")]
    begin, working = load_begin_working(pass_dir)
    actions = list(working.get("actions") or [])
    actions.extend(
        {
            "step": (
                "reap_stale_worktree" if row.get("removed") else "keep_stale_worktree"
            ),
            **row,
        }
        for row in rows
    )
    working["actions"] = actions
    save_begin_working(pass_dir, begin, working)
    archives = _archive_gc(config_path=config_path, live=live)
    return {
        "ok": True,
        "result": {
            "pass_dir": pass_dir,
            "planned": not live,
            "kept": kept,
            "reaped": reaped,
            "failed": [x for x in kept if x.get("reason") == "remove_failed"],
            "kept_count": len(kept) + len(collected.get("deferred") or []),
            "reaped_count": len(reaped),
            "deferred": list(collected.get("deferred") or []),
            "receipt_state_unknown": not bool(collected.get("receipt_safe", True)),
            "bounded": bool(catalog.get("bounded")),
            "archives": archives,
        },
    }


def summarize(
    *,
    pass_dir: str,
    collected: dict,
    catalog: dict,
    live: bool,
    config_path: str | None = None,
) -> dict:
    """Persist catalog effects (or empty) and always run archive TTL GC."""
    if not collected.get("ok"):
        return dict(collected)
    if not catalog.get("ok", True) and not catalog.get("effects"):
        return dict(catalog)
    return persist_result(
        pass_dir=pass_dir,
        collected=collected,
        catalog=catalog,
        live=live,
        config_path=config_path,
    )
