"""Select at most one non-manual CONFLICTING or DIRTY PR."""

from lokay.passkit.support import is_manual_pr
from lokay.passkit.working import load_begin_working


def select(*, pass_dir: str) -> dict:
    begin, working = load_begin_working(pass_dir)
    prs = dict(working.get("prs_by_repo") or {})
    for repo in list(begin.get("repos") or []):
        for pr in list(prs.get(repo) or []):
            if not is_manual_pr(pr) and str(pr.get("mergeable") or "").upper() in {
                "CONFLICTING",
                "DIRTY",
            }:
                return {
                    "ok": True,
                    "route": "conflict",
                    "repo": repo,
                    "pr": int(pr["number"]),
                    "head_ref": str(pr.get("head_ref") or ""),
                    "mergeable": str(pr.get("mergeable") or "").upper(),
                    "title": str(pr.get("title") or ""),
                }
    return {"ok": True, "route": "none"}
