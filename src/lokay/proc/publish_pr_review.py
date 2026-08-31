"""Publish one selected SHA-bound PR-review result."""
from __future__ import annotations
import argparse, json
from lokay.envelope import emit_exit, err, ok
from lokay.pr_review import decision_from_dict, decide_review_merge
from lokay.pr_review_io import publish_decision, publish_fail_closed
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner

def publish(*, cfg, repo: str, pr: int, evidence: dict, selected: dict, live: bool) -> dict:
    route=str(selected.get("route") or "")
    if route in {"cached", "policy"}: return ok(repo=repo,pr=pr,head_sha=str(evidence.get("head_sha") or ""),decision=dict(selected.get("decision") or {}),merge_ok=bool(selected.get("merge_ok")),execution={"source":"cache" if route == "cached" else "policy"})
    mutate=mutations_allowed(live_flag=live,cfg=cfg)
    if route == "needs_human":
        applied=publish_fail_closed(runner(cfg),repo,pr,ValueError(str(selected.get("validation_error") or "invalid review JSON")),mutate=mutate)
        return ok(repo=repo,pr=pr,head_sha=str(evidence.get("head_sha") or ""),decision={"verdict":"needs_human"},merge_ok=False,reason=str(selected.get("reason") or "review_validation_exhausted"),applied=applied,execution={"source":"agent_retry_exhausted"})
    if route != "publish": return err(f"unknown selected review route: {route}")
    decision=decision_from_dict(dict(selected.get("decision") or {})); prior=int(selected.get("request_changes_count") or 0); limit=max(1,int(getattr(cfg,"max_request_changes_per_pr",2))); merge_ok,escalated=decide_review_merge(decision,prior,max_request_changes=limit)
    style_target = cfg.review_style_for(repo) if hasattr(cfg, "review_style_for") else ""
    publish_decision(runner(cfg),repo,pr,decision,head_sha=str(evidence.get("head_sha") or ""),merge_ok=merge_ok,escalated=escalated,mutate=mutate,style_target=style_target)
    return ok(repo=repo,pr=pr,head_sha=str(evidence.get("head_sha") or ""),decision=decision.to_dict(),merge_ok=merge_ok,escalated=escalated,applied=mutate,request_changes_count=prior+(1 if decision.verdict=="request_changes" else 0),execution={"source":"agent"})

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-publish-pr-review"); add_config_live(p); p.add_argument("--repo",required=True); p.add_argument("--pr",required=True,type=int); p.add_argument("--evidence-json",required=True); p.add_argument("--selected-json",required=True); a=p.parse_args(argv)
    try: evidence=json.loads(a.evidence_json); selected=json.loads(a.selected_json)
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid publish input JSON: {exc}"))
    return emit_exit(publish(cfg=load_cfg(a),repo=a.repo,pr=a.pr,evidence=evidence,selected=selected,live=bool(a.live)))
if __name__=="__main__": raise SystemExit(main())
