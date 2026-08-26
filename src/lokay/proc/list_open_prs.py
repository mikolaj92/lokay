"""LEAF: list live open mill PRs. Two small functions, no child graph."""

from __future__ import annotations

import argparse
import json

from lokay.proc._common import load_cfg, runner
from lokay.runner import gh_spec


def _list_open(repos: list[str], *, live: bool) -> dict:
    git = runner()
    rows: list[dict] = []
    for repo in repos:
        result = git.run(
            gh_spec(
                [
                    "pr",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    "open",
                    "--json",
                    "number,title,headRefName,url",
                    "--limit",
                    "1000",
                ],
                timeout_seconds=60,
            ),
            live=live,
        )
        if not live:
            continue
        if result.returncode != 0:
            text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            return {
                "ok": False,
                "error": text or f"open PR list failed for {repo}",
                "repo": repo,
            }
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error": f"open PR list JSON failed for {repo}: {exc}",
                "repo": repo,
            }
        if not isinstance(payload, list):
            return {
                "ok": False,
                "error": f"open PR list on {repo} returned non-list JSON",
                "repo": repo,
            }
        for row in payload:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "repo": repo,
                    "pr": int(row["number"]),
                    "title": str(row.get("title") or ""),
                    "branch": str(row.get("headRefName") or ""),
                }
            )
    return {"ok": True, "prs": rows}


def _keep_mill(rows: list[dict], prefix: str) -> list[dict]:
    stem = prefix.rstrip("/") + "/"
    return [
        dict(row)
        for row in rows
        if str(row.get("branch") or "").startswith(stem)
    ]


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    listed = _list_open([repo.name for repo in cfg.active_repos()], live=live)
    if listed.get("ok") is False:
        return listed
    kept = _keep_mill(list(listed.get("prs") or []), str(cfg.branch_prefix or "ai/fix"))
    return {"ok": True, "prs": kept, "count": len(kept)}
