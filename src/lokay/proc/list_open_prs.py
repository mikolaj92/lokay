"""List open PRs from GitHub. One function, no 30-slot catalog."""

from __future__ import annotations

import argparse
import json

from lokay.proc._common import load_cfg, runner
from lokay.runner import gh_spec


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
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
                    "50",
                ],
                timeout_seconds=60,
            ),
            live=live,
        )
        if not live:
            continue
        if result.returncode != 0:
            continue
        for row in json.loads(result.stdout or "[]"):
            rows.append(
                {
                    "repo": repo.name,
                    "pr": int(row["number"]),
                    "title": str(row.get("title") or ""),
                    "branch": str(row.get("headRefName") or ""),
                }
            )
    return {"ok": True, "prs": rows, "count": len(rows)}
