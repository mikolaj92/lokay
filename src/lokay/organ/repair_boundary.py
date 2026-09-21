"""Fala bindings for the explicit PR-repair boundary."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from lokay.config import load_config

_ATOMS = frozenset(
    {
        "admit_pr_repair",
        "checkpoint_repair_publication",
        "probe_pr_state",
        "validate_initial_repair",
        "pr_repair_retry_agent",
        "validate_repair_retry",
        "select_initial_repair",
        "collect_repair_pr_metadata",
        "collect_repair_changed_files",
        "collect_repair_test_contract",
        "collect_repair_review_findings",
        "evidence_repair_agent",
        "validate_evidence_repair",
        "select_evidence_repair",
        "finalize_repair_result",
        "pr_repair_fail_closed",
        "select_repair_test",
        "pr_test_repair_agent",
        "validate_test_repair",
        "select_test_repair_result",
        "select_repair_test_recheck",
        "finalize_repair_tests",
        "pr_repair_terminal",
        "summarize_pr_repair",
    }
)


def handle_repair_boundary(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom not in _ATOMS:
        return None
    if atom == "checkpoint_repair_publication":
        from lokay.proc.pr_repair_checkpoint import persist
        from lokay.proc.pr_repair_receipts import resolve_budget, resolve_state_dir

        if not inputs.get("live"):
            return {"ok": True, "route": "checkpointed", "planned": True}
        config = str(inputs.get("config_path") or "")
        state = resolve_state_dir(config)
        if state is None:
            return {"ok": True, "route": "fail_closed", "reason": "repair_checkpoint_state_missing"}
        return persist(inputs=inputs, run_ref=dict(inputs.get("repair_run_ref") or {}),
                       state_dir=state, budget=resolve_budget(config))
    if atom in {"admit_pr_repair", "probe_pr_state"}:
        from lokay.proc.admit_pr_repair import admit_live
        from lokay.proc.probe_pr_state import probe as probe_pr

        repo = str(inputs.get("repo") or ctx.get("repo") or "")
        pr = int(inputs.get("pr") or inputs.get("pr_number") or ctx.get("pr_number") or 0)
        live = bool(inputs.get("live"))
        if atom == "probe_pr_state":
            return probe_pr(repo=repo, pr=pr, live=live)
        return admit_live(repo=repo, pr=pr, live=live)
    worktree = Path(str((up.get("worktree_add") or {}).get("worktree") or ""))
    cfg = load_config(inputs.get("config_path") or inputs.get("config"))
    live = bool(inputs.get("live"))
    repo = ctx["repo"]
    pr = int(ctx["pr_number"] or 0)
    if atom in {
        "validate_initial_repair",
        "validate_repair_retry",
        "validate_evidence_repair",
        "validate_test_repair",
    }:
        from lokay.proc.validate_repair_result import validate

        source = {
            "validate_initial_repair": "run_agent",
            "validate_repair_retry": "pr_repair_retry_agent",
            "validate_evidence_repair": "evidence_repair_agent",
            "validate_test_repair": "pr_test_repair_agent",
        }[atom]
        value = up.get(source) or {}
        return validate(str(value.get("stdout") or value.get("stdout_tail") or ""))
    if atom == "pr_repair_retry_agent":
        from lokay.proc.run_pr_repair_retry_agent import execute

        value = up.get("validate_initial_repair") or {}
        return execute(
            cfg=cfg,
            worktree=worktree,
            error=str(value.get("validation_error") or "invalid JSON"),
            stdout=str(value.get("agent_stdout_tail") or ""),
            live=live,
        )
    if atom == "select_initial_repair":
        from lokay.proc.select_initial_repair import select

        return select(
            up.get("validate_initial_repair") or {},
            up.get("validate_repair_retry") or {},
        )
    if atom.startswith("collect_repair_"):
        if atom == "collect_repair_test_contract":
            from lokay.proc.collect_repair_test_contract import collect

            return collect(str(worktree))
        if atom == "collect_repair_review_findings":
            from lokay.proc.collect_repair_review_findings import collect

            return collect(dict(inputs.get("review") or {}))
        module = __import__(f"lokay.proc.{atom}", fromlist=["collect"])
        return module.collect(repo=repo, pr=pr, live=live)
    if atom == "evidence_repair_agent":
        from lokay.proc.run_evidence_repair_agent import execute

        names = (
            "collect_repair_pr_metadata",
            "collect_repair_changed_files",
            "collect_repair_test_contract",
            "collect_repair_review_findings",
        )
        supplement = next((up.get(name) for name in names if up.get(name)), {})
        return execute(
            cfg=cfg, worktree=worktree, evidence=dict(supplement or {}), live=live
        )
    if atom == "select_evidence_repair":
        from lokay.proc.select_evidence_repair import select

        return select(
            up.get("select_initial_repair") or {},
            up.get("validate_evidence_repair") or {},
        )
    if atom == "finalize_repair_result":
        from lokay.proc.finalize_repair_result import finalize_result

        return finalize_result(
            up.get("select_initial_repair") or {},
            up.get("select_evidence_repair") or {},
        )
    if atom == "summarize_pr_repair":
        from lokay.proc.summarize_pr_repair import summarize

        selected = dict(inputs.get("select_pr_repair_department") or {})
        selected_review = dict(selected.get("review", inputs.get("review")) or {})
        # Overlay by key presence: explicit empty CI authority must override
        # retained approval evidence and any less-specific input handoff.
        handoff = {**inputs, **selected}
        selected_task = dict(handoff.get("task") or {})
        repair_kind = str(selected.get("repair_kind") or inputs.get("repair_kind") or "")
        start_head_sha = str(
            selected.get("repair_start_head_sha") or inputs.get("repair_start_head_sha")
            or inputs.get("head_sha") or ""
        )
        return summarize(
            final=up.get("finalize_repair_tests") or {},
            push=up.get("push") or {},
            repo=repo,
            pr=pr,
            branch=str(inputs.get("branch") or ""),
            admit=up.get("admit_pr_repair") or {},
            worktree=up.get("worktree_add") or {},
            repair_handoff={
                "kind": repair_kind,
                "start_head_sha": start_head_sha,
                "head_sha": str(selected.get("head_sha") or inputs.get("head_sha") or ""),
                "task": selected_task,
                "findings": list(handoff.get("findings") or []),
                "reviewed_head_sha": str(handoff.get("reviewed_head_sha") or ""),
                "task_identity_sha256": str(handoff.get("task_identity_sha256") or ""),
                "review_result_sha256": str(handoff.get("review_result_sha256", selected_review.get("review_result_sha256")) or ""),
                "repair_push_intent_sha256": str((up.get("push") or {}).get("repair_push_intent_sha256") or ""),
                **({"repair_kind": repair_kind, "head_sha": start_head_sha}
                   if repair_kind == "ci" else {}),
            },
        )
    if atom in {"pr_repair_fail_closed", "pr_repair_terminal"}:
        from lokay.proc.repair_terminal import terminal

        source = (
            "finalize_repair_result"
            if atom == "pr_repair_fail_closed"
            else "finalize_repair_tests"
        )
        return terminal(
            dict((up.get(source) or {}).get("decision") or {}),
            kind="fail_closed" if atom == "pr_repair_fail_closed" else "repair_exhausted",
        )
    if atom in {"select_repair_test", "select_repair_test_recheck"}:
        from lokay.proc.select_repair_test import select

        if atom == "select_repair_test":
            return select(
                up.get("test_local") or {},
                applicable=(up.get("finalize_repair_result") or {}).get("route")
                == "repaired",
            )
        return select(
            up.get("test_local_recheck") or {},
            applicable=(up.get("select_test_repair_result") or {}).get("route")
            == "repaired",
        )
    if atom == "pr_test_repair_agent":
        from lokay.proc.run_pr_test_repair_agent import execute

        return execute(
            cfg=cfg, worktree=worktree, test=up.get("test_local") or {}, live=live
        )
    if atom == "select_test_repair_result":
        from lokay.proc.select_test_repair_result import select

        return select(
            up.get("validate_test_repair") or {},
            applicable=(up.get("select_repair_test") or {}).get("route") == "fail",
        )
    if atom == "finalize_repair_tests":
        from lokay.proc.finalize_repair_tests import finalize

        return finalize(
            up.get("select_repair_test") or {},
            up.get("select_repair_test_recheck") or {},
            applicable=(up.get("finalize_repair_result") or {}).get("route")
            == "repaired",
        )
    raise AssertionError(atom)
