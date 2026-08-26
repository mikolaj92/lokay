"""List live open PRs from GitHub for the authored repo scope. No mill filter."""

from __future__ import annotations

import json

from lokay.proc._common import runner
from lokay.runner import gh_spec


def run(scope: dict, *, live: bool) -> dict:
    if scope.get("ok") is False:
        return {
            "ok": False,
            "error": scope.get("error") or "PR scope failed",
            "prs": [],
            "count": 0,
        }
    git = runner()
    rows: list[dict] = []
    for name in list(scope.get("repos") or []):
        repo = str(name)
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
    return {"ok": True, "prs": rows, "count": len(rows)}
