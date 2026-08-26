"""List live open mill PRs from GitHub. No 30-slot catalog."""

from __future__ import annotations

import argparse
import json

from lokay.proc._common import load_cfg, runner
from lokay.runner import gh_spec


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
    prefix = str(cfg.branch_prefix or "ai/fix").rstrip("/") + "/"
    rows: list[dict] = []
    for repo in cfg.active_repos():
        result = git.run(
            gh_spec(
                [
                    "pr",
                    "list",
                    "--repo",
                    repo.name,
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
                "error": text or f"open PR list failed for {repo.name}",
                "repo": repo.name,
            }
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error": f"open PR list JSON failed for {repo.name}: {exc}",
                "repo": repo.name,
            }
        if not isinstance(payload, list):
            return {
                "ok": False,
                "error": f"open PR list on {repo.name} returned non-list JSON",
                "repo": repo.name,
            }
        for row in payload:
            if not isinstance(row, dict):
                continue
            branch = str(row.get("headRefName") or "")
            if not branch.startswith(prefix):
                continue
            rows.append(
                {
                    "repo": repo.name,
                    "pr": int(row["number"]),
                    "title": str(row.get("title") or ""),
                    "branch": branch,
                }
            )
    return {"ok": True, "prs": rows, "count": len(rows)}
