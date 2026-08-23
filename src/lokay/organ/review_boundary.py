"""Fala bindings for the SHA-bound PR-review subgraph."""
from __future__ import annotations
from typing import Any


def handle_review_boundary(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    owned = {
        "collect_pr_review_evidence", "resolve_sha_review", "pr_review_agent",
        "validate_pr_review", "pr_review_retry_agent", "validate_pr_review_retry",
        "select_pr_review", "publish_pr_review",
    }
    if atom not in owned:
        return None
    repo=str(ctx["repo"]); pr=int(ctx["pr_number"]); branch=str(ctx["branch"]); live=bool(ctx["live"]); config=str(inputs.get("config_path") or "") or None
    if atom == "collect_pr_review_evidence":
        from lokay.proc.collect_pr_review_evidence import collect
        checks=up.get("pr_checks") or {}
        return collect(repo=repo,pr=pr,branch=branch,live=live,checks_text=str(checks.get("text") or ""))
    if atom == "resolve_sha_review":
        from lokay.config import load_config
        from lokay.review_boundary import resolve_sha_review
        if not load_config(config).require_llm_review:
            return {"ok": True, "route": "policy", "decision": {"verdict": "approve"}, "merge_ok": True, "request_changes_count": 0}
        return resolve_sha_review(dict((up.get("collect_pr_review_evidence") or {}).get("evidence") or {}))
    if atom in {"pr_review_agent", "pr_review_retry_agent"}:
        from lokay.proc.run_pr_review_agent import run_review_agent
        evidence=dict((up.get("collect_pr_review_evidence") or {}).get("evidence") or {})
        feedback=up.get("validate_pr_review") if atom == "pr_review_retry_agent" else None
        return run_review_agent(config_path=config,repo=repo,pr=pr,evidence=evidence,live=live,feedback=feedback)
    if atom in {"validate_pr_review", "validate_pr_review_retry"}:
        from lokay.review_boundary import validate_review_output
        if atom == "validate_pr_review" and (up.get("resolve_sha_review") or {}).get("route") in {"cached", "policy"}:
            return {"ok": True, "route": "not_applicable"}
        source="pr_review_retry_agent" if atom.endswith("retry") else "pr_review_agent"
        return validate_review_output(str((up.get(source) or {}).get("stdout") or ""))
    if atom == "select_pr_review":
        from lokay.review_boundary import select_review_decision
        return select_review_decision(up.get("resolve_sha_review") or {},up.get("validate_pr_review") or {},up.get("validate_pr_review_retry") or {})
    if atom == "publish_pr_review":
        from lokay.config import load_config
        from lokay.proc.publish_pr_review import publish
        evidence=dict((up.get("collect_pr_review_evidence") or {}).get("evidence") or {})
        return publish(cfg=load_config(config),repo=repo,pr=pr,evidence=evidence,selected=up.get("select_pr_review") or {},live=live)
    return None
