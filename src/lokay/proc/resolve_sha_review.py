"""Resolve a durable review result for the current PR head SHA."""
from __future__ import annotations
import argparse, json
from lokay.envelope import emit_exit, err
from lokay.review_boundary import resolve_sha_review

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-resolve-sha-review"); p.add_argument("--evidence-json",required=True); a=p.parse_args(argv)
    try: evidence=json.loads(a.evidence_json)
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid evidence JSON: {exc}"))
    return emit_exit(resolve_sha_review(evidence))
if __name__=="__main__": raise SystemExit(main())
