"""Fala bindings for the SHA-bound PR-review subgraph."""
from __future__ import annotations
from typing import Any

OWNED = frozenset({
    "collect_pr_review_evidence", "resolve_sha_review", "pr_review_agent",
    "validate_pr_review", "pr_review_retry_agent", "validate_pr_review_retry",
    "select_pr_review", "review_evidence_catalog", "evidence_review_agent",
    "validate_evidence_review", "select_evidence_review",
    "finalize_pr_review", "publish_pr_review",
})


def _sieve_not_review(up: dict[str, dict[str, Any]]) -> bool:
    return str((up.get("classify_pr_triage_checks") or {}).get("route") or "") in {
        "repair",
        "wait",
    }


def handle_review_boundary(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    if atom not in OWNED:
        return None
    if atom != "collect_pr_review_evidence" and _sieve_not_review(up):
        return {
            "ok": True,
            "route": "not_applicable",
            "reason": "pr_triage_not_review",
            "evidence_kind": "none",
            "decision": {"verdict": "not_applicable"},
        }
    repo, pr = str(ctx["repo"]), int(ctx["pr_number"])
    branch, live = str(ctx["branch"]), bool(ctx["live"])
    config = str(inputs.get("config_path") or "") or None
    evidence = dict((up.get("collect_pr_review_evidence") or {}).get("evidence") or {})
    if atom == "resolve_sha_review":
        evidence["config_path"] = config or ""
    if atom == "collect_pr_review_evidence":
        from lokay.proc.collect_pr_review_evidence import collect
        return collect(repo=repo,pr=pr,branch=branch,live=live,checks_text=str((up.get("pr_checks") or {}).get("text") or ""),config_path=config)
    if atom == "resolve_sha_review":
        from lokay.review_boundary import resolve_structured_sha_review
        return resolve_structured_sha_review(evidence)
    if atom == "pr_review_agent":
        if str((up.get("resolve_sha_review") or {}).get("route") or "") != "agent":
            return {"ok": True, "route": "not_applicable", "reason": "review_agent_not_selected"}
        from lokay.proc.run_pr_review_agent import run_review_agent
        result = run_review_agent(config_path=config,repo=repo,pr=pr,evidence=evidence,live=live)
        if not result.get("ok"):
            return {"ok": True, "route": "complete", "stdout": "", "plugin_error": str(result.get("reason") or result.get("error") or "plugin failed")}
        return result
    if atom == "pr_review_retry_agent":
        return {"ok": True, "route": "not_applicable", "stdout": ""}
    if atom == "evidence_review_agent":
        from lokay.proc.run_evidence_review_agent import run
        additional=dict((up.get("review_evidence_catalog") or {}).get("additional_evidence") or {})
        return run(config_path=config,repo=repo,pr=pr,evidence=evidence,additional=additional,live=live)
    if atom in {"validate_pr_review", "validate_pr_review_retry", "validate_evidence_review"}:
        from lokay.proc.validate_pr_review import validate_result
        if atom != "validate_pr_review":
            if atom == "validate_evidence_review" and (up.get("select_pr_review") or {}).get("route") == "evidence":
                return {"ok": True, "route": "fail_closed", "reason": "structured_evidence_review_unsupported"}
            return {"ok": True, "route": "not_applicable"}
        source = up.get("pr_review_agent") or {}
        if source.get("plugin_error"):
            from lokay.proc.pr_review_plugin import classified_host_failure_code
            error = str(source.get("plugin_error") or "")
            mapped = classified_host_failure_code(error)
            code, _, detail = mapped.partition(": ")
            if (
                code.isascii()
                and code.replace("_", "").isalnum()
                and code[0:1].isalpha()
                and len(code) <= 64
            ):
                reason = (
                    f"{code}: {detail}"
                    if detail and detail.isascii() and 0 < len(detail) <= 200
                    else code
                )
            else:
                reason = "review_plugin_failed"
            return {"ok": True, "route": "fail_closed", "reason": reason}
        if (up.get("resolve_sha_review") or {}).get("route") == "cached":
            return {"ok": True, "route": "not_applicable"}
        result = source.get("result")
        request = source.get("request")
        if not isinstance(request, dict):
            return {"ok": True, "route": "fail_closed", "reason": "review_request_missing"}
        validated = validate_result(result if isinstance(result, dict) else {}, request)
        if validated.get("route") == "valid":
            execution = dict(result.get("evidence") or {}).get("upstream_execution") or {}
            decision = dict(validated.get("decision") or {})
            decision.update(
                review_input_fingerprint_sha256=str((result.get("evidence") or {}).get("input_fingerprint_sha256") or ""),
                review_preview_sha256=str((result.get("evidence") or {}).get("preview_sha256") or ""),
                review_rule_config_sha256=str(execution.get("rule_config_sha256") or ""),
                review_runtime_config_sha256=str(execution.get("runtime_config_sha256") or ""),
            )
            validated = {**validated, "decision": decision}
        return {**validated, "request_changes_count": int((up.get("resolve_sha_review") or {}).get("request_changes_count") or 0)}
    if atom == "select_pr_review":
        from lokay.review_boundary import select_structured_review
        resolved = up.get("resolve_sha_review") or {}
        validated = up.get("validate_pr_review") or {}
        if validated.get("route") == "fail_closed":
            return {"ok": True, "route": "fail_closed", "decision": {"verdict": "fail_closed"}, "reason": str(validated.get("reason") or "review_plugin_failed")}
        return select_structured_review(resolved, validated)
    if atom == "review_evidence_catalog":
        from lokay.proc.review_evidence_catalog import run
        return run(
            up.get("select_pr_review") or {},
            repo=repo,
            pr=pr,
            live=live,
            expected_sha=str(evidence.get("head_sha") or ""),
        )
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
