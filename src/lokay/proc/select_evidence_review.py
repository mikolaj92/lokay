"""Select the bounded evidence-review result."""
from __future__ import annotations
import argparse,json
from lokay.envelope import emit_exit,err
from lokay.review_boundary import select_evidence_review

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-select-evidence-review"); p.add_argument("--selected-json",required=True); p.add_argument("--validation-json",required=True); a=p.parse_args(argv)
    try: selected=json.loads(a.selected_json); validation=json.loads(a.validation_json)
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid evidence review JSON: {exc}"))
    return emit_exit(select_evidence_review(selected,validation))
if __name__=="__main__": raise SystemExit(main())
