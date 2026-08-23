"""Validate one agent response against the closed PR-review schema."""
from __future__ import annotations
import argparse
from lokay.envelope import emit_exit
from lokay.review_boundary import validate_review_output

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-validate-pr-review"); p.add_argument("--stdout",required=True); a=p.parse_args(argv)
    return emit_exit(validate_review_output(a.stdout))
if __name__=="__main__": raise SystemExit(main())
