"""Select cached, first-valid, retried-valid, or exhausted PR review."""
from __future__ import annotations
import argparse, json
from lokay.envelope import emit_exit, err
from lokay.review_boundary import select_review_decision

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-select-pr-review")
    for n in ("resolved","first","retry"): p.add_argument(f"--{n}-json",required=True)
    a=p.parse_args(argv)
    try: values=[json.loads(getattr(a,f"{n}_json")) for n in ("resolved","first","retry")]
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid review boundary JSON: {exc}"))
    return emit_exit(select_review_decision(*values))
if __name__=="__main__": raise SystemExit(main())
