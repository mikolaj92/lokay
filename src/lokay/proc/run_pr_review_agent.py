"""Run one read-only PR-review agent call from a collected evidence snapshot."""
from __future__ import annotations
import argparse, json
from lokay.agent import run_agent
from lokay.envelope import emit_exit, err, ok
from lokay.pr_review import review_prompt
from lokay.pr_review_io import review_worktree
from lokay.proc._common import add_config_live, agent_execute_allowed, load_cfg, runner
from lokay.review_boundary import validation_feedback_prompt

def run_review_agent(*, config_path: str | None, repo: str, pr: int, evidence: dict, live: bool, feedback: dict | None = None) -> dict:
    from lokay.config import load_config
    cfg=load_config(config_path); execute=agent_execute_allowed(cfg,live_flag=live)
    prompt=review_prompt(repo=repo,pr_number=pr,title=str(evidence.get("title") or ""),body=str(evidence.get("body") or ""),head_ref=str(evidence.get("head") or ""),diff_text=str(evidence.get("diff") or ""),checks_text=str(evidence.get("checks_text") or ""))
    if feedback:
        prompt += "\n\n" + validation_feedback_prompt(str(feedback.get("validation_error") or "invalid output"),str(feedback.get("agent_stdout_tail") or ""))
    agent=run_agent(runner(cfg),cfg,worktree=review_worktree(cfg,repo),prompt=prompt,execute=execute and live)
    if agent.get("status") == "failed": return err("pr_review agent failed",agent=agent)
    return ok(repo=repo,pr=pr,head_sha=str(evidence.get("head_sha") or ""),agent=agent,stdout=str(agent.get("stdout_tail") or ""))

def main(argv=None):
    p=argparse.ArgumentParser(prog="lokay-run-pr-review-agent"); add_config_live(p)
    p.add_argument("--repo",required=True); p.add_argument("--pr",required=True,type=int); p.add_argument("--evidence-json",required=True); p.add_argument("--feedback-json",default="")
    a=p.parse_args(argv)
    try: evidence=json.loads(a.evidence_json); feedback=json.loads(a.feedback_json) if a.feedback_json else None
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid PR review input JSON: {exc}"))
    return emit_exit(run_review_agent(config_path=a.config,repo=a.repo,pr=a.pr,evidence=evidence,live=bool(a.live),feedback=feedback))
if __name__=="__main__": raise SystemExit(main())
