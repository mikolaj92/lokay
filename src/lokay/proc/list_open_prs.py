"""LEAF: list live open lokay PRs. Two small functions, no child graph."""

from __future__ import annotations

import argparse

from lokay.proc._common import load_cfg, runner
from lokay.source import load_code


def _list_open(cfg, repos, *, live: bool) -> dict:
    git = runner()
    rows: list[dict] = []
    for repo in repos:
        try:
            contract = load_code(repo, runner=git, config=cfg, live=live)
            for change in contract.pr.list_open():
                rows.append(
                    {
                        "repo": change.target.id,
                        "pr": int(change.number),
                        "title": str(change.title or ""),
                        "branch": str(change.head or ""),
                        "head_sha": str(change.head_sha or ""),
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
    from lokay.proc.delivery_closeout import pending

    intents = pending(cfg.state_path) if live else []
    active = {repo.name for repo in cfg.active_repos()}
    intents = [intent for intent in intents if intent['repo'] in active]
    if listed.get("ok") is False and not intents:
        return listed
    kept = _keep_lokay(list(listed.get("prs") or []), str(cfg.branch_prefix or "ai/fix"))
    replay_ids = {(intent['repo'], intent['pr']) for intent in intents}
    kept = [row for row in kept if (row['repo'], row['pr']) not in replay_ids]
    kept.extend({**{key: intent[key] for key in ('repo', 'pr', 'branch', 'head_sha')},
                 'delivery_replay': True, 'closeout_intent': intent} for intent in intents)
    return {"ok": True, "prs": kept, "count": len(kept)}
