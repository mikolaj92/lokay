"""Choose the direct or evidence-enriched final PR review result."""
from __future__ import annotations
import argparse,json
from lokay.envelope import emit_exit,err
from lokay.review_boundary import finalize_review_selection

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-finalize-pr-review"); p.add_argument("--selected-json",required=True); p.add_argument("--evidence-selected-json",required=True); a=p.parse_args(argv)
    try: selected=json.loads(a.selected_json); evidence=json.loads(a.evidence_selected_json)
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid final review JSON: {exc}"))
    return emit_exit(finalize_review_selection(selected,evidence))
if __name__=="__main__": raise SystemExit(main())
