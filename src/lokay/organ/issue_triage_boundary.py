"""Fala bindings for the explicit issue-triage state boundary."""

from __future__ import annotations
import os
from typing import Any
from lokay.config import load_config
from lokay.proc._common import mutations_allowed, resolve_repo_clone, runner

OWNED = frozenset(
    {
        "resolve_issue_candidate",
        "collect_issue_linked_prs",
        "collect_issue_covering_prs",
        "resolve_issue_hard_facts",
        "issue_triage_agent",
        "validate_issue_triage",
        "issue_triage_retry_agent",
        "validate_issue_triage_retry",
        "select_issue_triage",
        "collect_issue_repo_shape",
        "collect_issue_named_paths",
        "verify_issue_evidence",
        "issue_evidence_agent",
        "validate_issue_evidence",
        "select_issue_evidence",
        "finalize_issue_triage",
        "apply_issue_ready",
        "apply_issue_close",
        "apply_issue_manual",
        "issue_split_subflow",
    }
)


def handle_issue_triage(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom not in OWNED:
        return None
    repo, number, live = str(ctx["repo"]), int(ctx["issue_number"]), bool(ctx["live"])
    cfg = load_config(str(inputs.get("config_path") or "") or None)
    mutate = mutations_allowed(live_flag=live, cfg=cfg)
    fetch = os.environ.get("LOKAY_OFFLINE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }
    issue = dict((up.get("get_issue") or {}).get("issue") or {})
    try:
        clone = resolve_repo_clone(cfg, repo)
    except KeyError:
        clone = None
    if atom == "resolve_issue_candidate":
        from lokay.issue_triage_boundary import resolve_candidate

        return resolve_candidate(
            issue,
            ready_label=cfg.ready_label,
            blocked_label=cfg.blocked_label,
            needs_feedback_label=cfg.needs_feedback_label,
        )
    if atom == "collect_issue_linked_prs":
        from lokay.proc.collect_issue_linked_prs import collect

        return collect(runner=runner(), repo=repo, issue_data=issue, live=fetch)
    if atom == "collect_issue_covering_prs":
        from lokay.proc.collect_issue_covering_prs import collect

        return collect(
            runner=runner(),
            repo=repo,
            issue=number,
            branch_prefix=cfg.branch_prefix,
            live=fetch,
        )
    if atom == "resolve_issue_hard_facts":
        from lokay.issue_triage_boundary import resolve_hard_facts

        linked = up.get("collect_issue_linked_prs") or {}
        covering = up.get("collect_issue_covering_prs") or {}
        candidate = up.get("resolve_issue_candidate") or {}
        if candidate.get("route") != "evaluate":
            return resolve_hard_facts(issue, candidate, linked, covering)
        if not linked.get("collected") or not covering.get("collected"):
            return {
                "ok": True,
                "route": "terminal",
                "decision": {
                    "verdict": "needs_human",
                    "reason": "hard_fact_evidence_unavailable",
                },
            }
        return resolve_hard_facts(issue, candidate, linked, covering)
    hard = up.get("resolve_issue_hard_facts") or {}
    if atom == "issue_triage_agent":
        from lokay.proc.run_issue_triage_agent import run

        return run(
            cfg=cfg,
            repo=repo,
            issue=number,
            issue_data=issue,
            hard_facts=hard,
            clone_path=clone,
            live=live,
        )
    if atom == "issue_triage_retry_agent":
        from lokay.proc.run_issue_triage_retry_agent import run

        return run(
            cfg=cfg,
            repo=repo,
            issue=number,
            issue_data=issue,
            hard_facts=hard,
            feedback=up.get("validate_issue_triage") or {},
            clone_path=clone,
            live=live,
        )
    if atom == "verify_issue_evidence":
        selected = up.get("select_issue_triage") or {}
        if selected.get("route") != "evidence":
            return {"ok": True, "route": "not_applicable"}
        kind = str(selected.get("evidence_kind") or "")
        source = {
            "repo_shape": "collect_issue_repo_shape",
            "named_paths": "collect_issue_named_paths",
            "linked_prs": "collect_issue_linked_prs",
            "covering_prs": "collect_issue_covering_prs",
        }.get(kind, "")
        chosen = up.get(source) or {}
        if not chosen.get("collected") or chosen.get("additional_evidence") is None:
            return {
                "ok": True,
                "route": "needs_human",
                "reason": "requested_issue_evidence_unavailable",
            }
        return {
            "ok": True,
            "route": "agent",
            "additional_evidence": {
                "kind": kind,
                "value": chosen["additional_evidence"],
            },
        }
    if atom == "issue_evidence_agent":
        from lokay.proc.run_issue_evidence_agent import run

        additional = dict(
            (up.get("verify_issue_evidence") or {}).get("additional_evidence") or {}
        )
        return run(
            cfg=cfg,
            repo=repo,
            issue=number,
            issue_data=issue,
            hard_facts=hard,
            additional=additional,
            clone_path=clone,
            live=live,
        )
    if atom in {
        "validate_issue_triage",
        "validate_issue_triage_retry",
        "validate_issue_evidence",
    }:
        from lokay.issue_triage_boundary import validate_output

        if atom == "validate_issue_triage" and hard.get("route") == "terminal":
            return {"ok": True, "route": "not_applicable"}
        source = {
            "validate_issue_triage": "issue_triage_agent",
            "validate_issue_triage_retry": "issue_triage_retry_agent",
            "validate_issue_evidence": "issue_evidence_agent",
        }[atom]
        return validate_output(str((up.get(source) or {}).get("stdout") or ""))
    if atom == "select_issue_triage":
        from lokay.issue_triage_boundary import select_initial

        return select_initial(
            hard,
            up.get("validate_issue_triage") or {},
            up.get("validate_issue_triage_retry") or {},
        )
    if atom == "collect_issue_repo_shape":
        from lokay.proc.collect_issue_repo_shape import collect

        return collect(clone_path=clone)
    if atom == "collect_issue_named_paths":
        from lokay.proc.collect_issue_named_paths import collect

        return collect(issue_data=issue, clone_path=clone)
    if atom == "select_issue_evidence":
        from lokay.issue_triage_boundary import select_evidence

        return select_evidence(
            up.get("select_issue_triage") or {}, up.get("validate_issue_evidence") or {}
        )
    if atom == "finalize_issue_triage":
        from lokay.issue_triage_boundary import finalize

        return finalize(
            up.get("select_issue_triage") or {}, up.get("select_issue_evidence") or {}
        )
    decision = dict(
        (up.get("plan_issue_split") or {}).get("decision")
        or (up.get("finalize_issue_triage") or {}).get("decision")
        or {}
    )
    if atom == "issue_split_subflow":
        from lokay.proc.issue_split_subflow import invoke

        return invoke(
            config_path=str(inputs.get("config_path") or "") or None,
            repo=repo,
            issue=number,
            decision=decision,
            live=mutate,
        )
    if atom == "apply_issue_ready":
        from lokay.proc.apply_issue_ready import apply

        return apply(
            runner=runner(),
            cfg=cfg,
            repo=repo,
            issue=number,
            issue_data=issue,
            live=mutate,
        )
    if atom == "apply_issue_close":
        from lokay.proc.apply_issue_close import apply

        return apply(
            runner=runner(), repo=repo, issue=number, decision=decision, live=mutate
        )
    if atom == "apply_issue_manual":
        from lokay.proc.apply_issue_manual import apply

        return apply(
            runner=runner(),
            cfg=cfg,
            repo=repo,
            issue=number,
            decision=decision,
            live=mutate,
        )
    return None
