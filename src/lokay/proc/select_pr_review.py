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
    selected = select_review_decision(*values)
    if selected.get("route") == "fail_closed":
        return emit_exit(selected)
    from lokay.proc.validate_pr_review import validate_result

    resolved, first, retry = values
    if resolved.get("route") == "cached":
        return emit_exit(selected)
    source = retry if first.get("route") == "retry" else first
    result = source.get("result")
    request = source.get("request")
    if not isinstance(result, dict) or not isinstance(request, dict):
        return emit_exit({
            "ok": True, "route": "fail_closed",
            "decision": {"verdict": "fail_closed"},
            "reason": "review_result_invalid",
        })
    validated = validate_result(result, request)
    if validated.get("route") != "valid":
        return emit_exit({
            "ok": True, "route": "fail_closed",
            "decision": {"verdict": "fail_closed"},
            "reason": str(validated.get("error") or "review_result_invalid"),
        })
    return emit_exit({**selected, "decision": validated["decision"]})
if __name__=="__main__": raise SystemExit(main())
