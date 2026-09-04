"""LEAF: list live open lokay PRs. Two small functions, no child graph."""

from __future__ import annotations

import argparse

from lokay.code import load_code, slot_from_repo
from lokay.proc._common import load_cfg, runner


def _list_open(cfg, repos, *, live: bool) -> dict:
    git = runner()
    rows: list[dict] = []
    for repo in repos:
        try:
            contract = load_code(slot_from_repo(repo), runner=git, config=cfg, live=live)
            for change in contract.pr.list_open():
                rows.append(
                    {
                        "repo": change.target.id,
                        "pr": int(change.number),
                        "title": str(change.title or ""),
                        "branch": str(change.head or ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": str(exc) or f"open PR list failed for {repo.name}",
                "repo": repo.name,
            }
    return {"ok": True, "prs": rows}


def _keep_lokay(rows: list[dict], prefix: str) -> list[dict]:
    stem = prefix.rstrip("/") + "/"
    return [
        dict(row)
        for row in rows
        if str(row.get("branch") or "").startswith(stem)
    ]


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    listed = _list_open(cfg, cfg.active_repos(), live=live)
    if listed.get("ok") is False:
        return listed
    kept = _keep_lokay(list(listed.get("prs") or []), str(cfg.branch_prefix or "ai/fix"))
    return {"ok": True, "prs": kept, "count": len(kept)}
