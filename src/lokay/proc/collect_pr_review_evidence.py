"""Read one PR evidence snapshot for a SHA-bound review."""
from __future__ import annotations
import argparse
from lokay.envelope import emit_exit, err, ok
from lokay.pr_review_io import load_pr_evidence
from lokay.proc._common import add_config_read, runner

def collect(*, repo: str, pr: int, branch: str, live: bool, checks_text: str = "") -> dict:
    try:
        return ok(repo=repo, pr=pr, evidence=load_pr_evidence(
            runner(), repo, pr, live=live, branch=branch, checks_text=checks_text,
        ))
    except Exception as exc:
        return err(f"failed to load PR review evidence: {exc}", repo=repo, pr=pr, probe_failed=True)

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-collect-pr-review-evidence"); add_config_read(p)
    p.add_argument("--repo",required=True); p.add_argument("--pr",required=True,type=int); p.add_argument("--branch",default=""); p.add_argument("--checks-text",default="")
    a=p.parse_args(argv); return emit_exit(collect(repo=a.repo,pr=a.pr,branch=a.branch,live=not a.offline,checks_text=a.checks_text))
if __name__=="__main__": raise SystemExit(main())
