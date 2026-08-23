"""Collect refreshed metadata evidence for one PR."""
from __future__ import annotations
from lokay.envelope import ok
from lokay.gh_prs import gh_json
from lokay.proc._common import runner

def collect(*, repo: str, pr: int, live: bool) -> dict:
    try:
        value=gh_json(runner(),["pr","view",str(pr),"--repo",repo,"--json","number,headRefOid,mergeable,isDraft,baseRefName,headRefName"],live=live)
    except Exception as exc:
        return ok(collected=False,reason=f"failed to collect metadata evidence: {exc}",probe_failed=True)
    return ok(collected=True,repo=repo,pr=pr,evidence_kind="pr_metadata",additional_evidence=value)


def main(argv=None):
    import argparse
    from lokay.envelope import emit_exit
    from lokay.proc._common import add_config_read
    parser=argparse.ArgumentParser(prog="lokay-collect-review-pr-metadata"); add_config_read(parser)
    parser.add_argument("--repo",required=True); parser.add_argument("--pr",required=True,type=int)
    args=parser.parse_args(argv)
    return emit_exit(collect(repo=args.repo,pr=args.pr,live=not args.offline))
if __name__ == "__main__": raise SystemExit(main())
