"""Run one initial read-only PR-review agent call."""
from __future__ import annotations
from lokay.config import load_config
from lokay.pr_review import review_prompt
from lokay.proc._pr_review_agent_runtime import execute

def run_review_agent(*, config_path: str | None, repo: str, pr: int, evidence: dict, live: bool) -> dict:
    cfg=load_config(config_path)
    prompt=review_prompt(repo=repo,pr_number=pr,title=str(evidence.get("title") or ""),body=str(evidence.get("body") or ""),head_ref=str(evidence.get("head") or ""),diff_text=str(evidence.get("diff") or ""),checks_text=str(evidence.get("checks_text") or ""))
    return execute(cfg=cfg,repo=repo,pr=pr,head_sha=str(evidence.get("head_sha") or ""),prompt=prompt,live=live)


def main(argv=None):
    import argparse, json
    from lokay.envelope import emit_exit, err
    from lokay.proc._common import add_config_live
    parser=argparse.ArgumentParser(prog="lokay-run-pr-review-agent"); add_config_live(parser)
    parser.add_argument("--repo",required=True); parser.add_argument("--pr",required=True,type=int); parser.add_argument("--evidence-json",required=True)
    args=parser.parse_args(argv)
    try: evidence=json.loads(args.evidence_json)
    except json.JSONDecodeError as exc: return emit_exit(err(f"invalid PR review input JSON: {exc}"))
    return emit_exit(run_review_agent(config_path=args.config,repo=args.repo,pr=args.pr,evidence=evidence,live=bool(args.live)))
if __name__ == "__main__": raise SystemExit(main())
