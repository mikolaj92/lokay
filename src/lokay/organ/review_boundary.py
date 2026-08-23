"""Fala bindings for the SHA-bound PR-review subgraph."""
from __future__ import annotations
from typing import Any

OWNED = frozenset({
    "collect_pr_review_evidence", "resolve_sha_review", "pr_review_agent",
    "validate_pr_review", "pr_review_retry_agent", "validate_pr_review_retry",
    "select_pr_review", "collect_review_pr_metadata", "collect_review_changed_files",
    "collect_review_diff_tail", "collect_review_commit_history", "verify_review_evidence_sha", "evidence_review_agent", "validate_evidence_review", "select_evidence_review",
    "finalize_pr_review", "publish_pr_review",
})


def handle_review_boundary(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    if atom not in OWNED:
        return None
    repo, pr = str(ctx["repo"]), int(ctx["pr_number"])
    branch, live = str(ctx["branch"]), bool(ctx["live"])
    config = str(inputs.get("config_path") or "") or None
    evidence = dict((up.get("collect_pr_review_evidence") or {}).get("evidence") or {})
    if atom == "collect_pr_review_evidence":
        from lokay.proc.collect_pr_review_evidence import collect
        return collect(repo=repo,pr=pr,branch=branch,live=live,checks_text=str((up.get("pr_checks") or {}).get("text") or ""))
    if atom == "resolve_sha_review":
        from lokay.config import load_config
        from lokay.review_boundary import resolve_sha_review
        if not load_config(config).require_llm_review:
            return {"ok":True,"route":"policy","decision":{"verdict":"approve"},"merge_ok":True,"request_changes_count":0}
        return resolve_sha_review(evidence)
    if atom == "pr_review_agent":
        from lokay.proc.run_pr_review_agent import run_review_agent
        return run_review_agent(config_path=config,repo=repo,pr=pr,evidence=evidence,live=live)
    if atom == "pr_review_retry_agent":
        from lokay.proc.run_pr_review_retry_agent import run
        return run(config_path=config,repo=repo,pr=pr,evidence=evidence,feedback=up.get("validate_pr_review") or {},live=live)
    if atom == "evidence_review_agent":
        from lokay.proc.run_evidence_review_agent import run
        additional=dict((up.get("verify_review_evidence_sha") or {}).get("additional_evidence") or {})
        return run(config_path=config,repo=repo,pr=pr,evidence=evidence,additional=additional,live=live)
    if atom in {"validate_pr_review", "validate_pr_review_retry", "validate_evidence_review"}:
        from lokay.review_boundary import validate_review_output
        if atom == "validate_pr_review" and (up.get("resolve_sha_review") or {}).get("route") in {"cached","policy"}:
            return {"ok":True,"route":"not_applicable"}
        source={"validate_pr_review":"pr_review_agent","validate_pr_review_retry":"pr_review_retry_agent","validate_evidence_review":"evidence_review_agent"}[atom]
        return validate_review_output(str((up.get(source) or {}).get("stdout") or ""))
    if atom == "select_pr_review":
        from lokay.review_boundary import select_review_decision
        return select_review_decision(up.get("resolve_sha_review") or {},up.get("validate_pr_review") or {},up.get("validate_pr_review_retry") or {})
    if atom in {"collect_review_pr_metadata", "collect_review_changed_files", "collect_review_diff_tail", "collect_review_commit_history"}:
        module=__import__(f"lokay.proc.{atom}",fromlist=["collect"])
        return module.collect(repo=repo,pr=pr,live=live)
    if atom == "verify_review_evidence_sha":
        if (up.get("select_pr_review") or {}).get("route") != "evidence":
            return {"ok":True,"route":"not_applicable"}
        from lokay.proc.verify_review_evidence_sha import verify
        chosen={}
        for source in ("collect_review_pr_metadata", "collect_review_changed_files", "collect_review_diff_tail", "collect_review_commit_history"):
            if (up.get(source) or {}).get("additional_evidence") is not None:
                chosen={"kind":source.removeprefix("collect_review_"),"value":up[source]["additional_evidence"]}
                break
        if not chosen:
            return {"ok":True,"route":"needs_human","reason":"requested_review_evidence_unavailable"}
        result=verify(repo=repo,pr=pr,expected_sha=str(evidence.get("head_sha") or ""),live=live)
        if result.get("route") == "agent":
            result["additional_evidence"]=chosen
        return result
    if atom == "select_evidence_review":
        from lokay.review_boundary import select_evidence_review
        return select_evidence_review(up.get("select_pr_review") or {},up.get("validate_evidence_review") or {})
    if atom == "finalize_pr_review":
        from lokay.review_boundary import finalize_review_selection
        return finalize_review_selection(up.get("select_pr_review") or {},up.get("select_evidence_review") or {})
    if atom == "publish_pr_review":
        from lokay.config import load_config
        from lokay.proc.publish_pr_review import publish
        return publish(cfg=load_config(config),repo=repo,pr=pr,evidence=evidence,selected=up.get("finalize_pr_review") or {},live=live)
    return None
