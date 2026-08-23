"""Collect complete paginated commit metadata for one PR."""
from __future__ import annotations
import json
from lokay.envelope import ok
from lokay.gh_prs import gh_text
from lokay.proc._common import runner

def collect(*, repo: str, pr: int, live: bool) -> dict:
    try:
        raw=gh_text(runner(),["api","--paginate","--slurp",f"repos/{repo}/pulls/{pr}/commits?per_page=100"],live=live,require_success=True)
        pages=json.loads(raw or "[]") if live else []
        commits=[row for page in pages for row in page]
    except Exception as exc:
        return ok(collected=False,reason=f"failed to collect commits evidence: {exc}",probe_failed=True)
    rows=[{"sha":str(row.get("sha") or ""),"message":str(((row.get("commit") or {}).get("message") or ""))[:200]} for row in commits]
    sample=rows if len(rows) <= 50 else rows[:25]+rows[-25:]
    return ok(collected=True,repo=repo,pr=pr,evidence_kind="commit_summary",additional_evidence={"total":len(rows),"complete":len(rows)<=50,"sample":sample})

def main(argv=None):
    import argparse
    from lokay.envelope import emit_exit
    from lokay.proc._common import add_config_read
    parser=argparse.ArgumentParser(prog="lokay-collect-review-commit-summary"); add_config_read(parser)
    parser.add_argument("--repo",required=True); parser.add_argument("--pr",required=True,type=int)
    args=parser.parse_args(argv)
    return emit_exit(collect(repo=args.repo,pr=args.pr,live=not args.offline))
if __name__ == "__main__": raise SystemExit(main())
