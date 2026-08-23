"""Fala bindings for the explicit issue implementation boundary."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from lokay.config import load_config

_ATOMS = frozenset(
    {
        "validate_coding_result",
        "coding_retry_agent",
        "validate_coding_retry",
        "select_coding_result",
        "collect_coding_issue_snapshot",
        "collect_coding_repo_structure",
        "collect_coding_test_contract",
        "collect_coding_localized_diff",
        "evidence_coding_agent",
        "validate_evidence_coding",
        "select_evidence_coding",
        "finalize_coding_result",
        "coding_manual",
        "select_local_test",
        "select_local_test_recheck",
        "finalize_local_tests",
        "coding_repair_terminal",
        "resolve_implementation_issue",
        "validate_repair_result",
        "select_repair_result",
        "issue_to_pr_subflow",
        "issue_to_pr_no_effect",
        "collect_existing_delivery_pr",
        "collect_resumed_source",
        "resolve_existing_delivery",
        "close_existing_delivery",
    }
)


def owns(atom: str) -> bool:
    return atom in _ATOMS


def handle_coding_boundary(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if not owns(atom):
        return None
    worktree = Path(str((up.get("worktree_add") or {}).get("worktree") or ""))
    if atom in {
        "validate_coding_result",
        "validate_coding_retry",
        "validate_evidence_coding",
        "validate_repair_result",
    }:
        from lokay.proc.validate_coding_result import validate

        source = {
            "validate_coding_result": "run_agent",
            "validate_coding_retry": "coding_retry_agent",
            "validate_evidence_coding": "evidence_coding_agent",
            "validate_repair_result": "repair_agent",
        }[atom]
        return validate(
            str(
                (up.get(source) or {}).get("stdout")
                or (up.get(source) or {}).get("stdout_tail")
                or ""
            )
        )
    if atom == "collect_existing_delivery_pr":
        from lokay.proc.collect_existing_delivery_pr import collect
        from lokay.proc._common import runner

        return collect(
            runner=runner(),
            repo=ctx["repo"],
            issue=int(ctx["issue_number"]),
            live=bool(inputs.get("live")),
        )
    if atom == "collect_resumed_source":
        from lokay.proc.collect_resumed_source import collect
        from lokay.proc._common import runner

        return collect(
            runner=runner(),
            repo=ctx["repo"],
            issue=int(ctx["issue_number"]),
            cwd=Path.cwd(),
            live=bool(inputs.get("live")),
        )
    if atom == "resolve_existing_delivery":
        from lokay.proc.resolve_existing_delivery import resolve

        return resolve(
            up.get("resolve_implementation_issue") or {},
            up.get("collect_existing_delivery_pr") or {},
            up.get("collect_resumed_source") or {},
        )
    if atom == "close_existing_delivery":
        from lokay.proc.close_existing_delivery import close

        return close(
            repo=ctx["repo"],
            issue=int(ctx["issue_number"]),
            config_path=inputs.get("config_path") or inputs.get("config"),
            live=bool(inputs.get("live")),
        )
    if atom == "issue_to_pr_subflow":
        from lokay.proc.issue_to_pr_subflow import invoke

        return invoke(
            config_path=inputs.get("config_path") or inputs.get("config"),
            repo=ctx["repo"],
            issue=int(ctx["issue_number"]),
            live=bool(inputs.get("live")),
            incident_fingerprint=str(inputs.get("incident_fingerprint") or ""),
        )
    if atom == "issue_to_pr_no_effect":
        from lokay.proc.issue_to_pr_no_effect import terminal

        return terminal(up.get("resolve_existing_delivery") or {})
    if atom == "resolve_implementation_issue":
        from lokay.proc.resolve_implementation_issue import resolve

        return resolve(dict((up.get("get_issue") or {}).get("issue") or {}))
    if atom == "select_repair_result":
        from lokay.proc.select_repair_result import select

        return select(
            up.get("validate_repair_result") or {},
            applicable=(up.get("select_local_test") or {}).get("route") == "fail",
        )
    if atom == "coding_retry_agent":
        from lokay.proc.run_coding_retry_agent import run

        first = up.get("validate_coding_result") or {}
        prompt = (
            "Your previous coding response JSON was invalid. Return ONLY the required closed JSON object. Validator feedback: %s\nInvalid response: %s"
            % (
                first.get("validation_error") or "invalid JSON",
                first.get("agent_stdout_tail") or "",
            )
        )
        return run(
            cfg=load_config(inputs.get("config_path") or inputs.get("config")),
            worktree=worktree,
            prompt=prompt,
            live=bool(inputs.get("live")),
        )
    if atom == "select_coding_result":
        from lokay.proc.select_coding_result import select

        return select(
            up.get("validate_coding_result") or {},
            up.get("validate_coding_retry") or {},
        )
    if atom.startswith("collect_coding_"):
        if atom == "collect_coding_issue_snapshot":
            from lokay.proc.collect_coding_issue_snapshot import collect

            return collect(dict((up.get("get_issue") or {}).get("issue") or {}))
        module = __import__(f"lokay.proc.{atom}", fromlist=["collect"])
        return module.collect(str(worktree))
    if atom == "evidence_coding_agent":
        from lokay.proc.run_evidence_coding_agent import execute

        supplement = next(
            (
                up.get(name)
                for name in (
                    "collect_coding_issue_snapshot",
                    "collect_coding_repo_structure",
                    "collect_coding_test_contract",
                    "collect_coding_localized_diff",
                )
                if up.get(name)
            ),
            {},
        )
        return execute(
            cfg=load_config(inputs.get("config_path") or inputs.get("config")),
            worktree=worktree,
            evidence=dict(supplement or {}),
            live=bool(inputs.get("live")),
        )
    if atom == "select_evidence_coding":
        from lokay.proc.select_evidence_coding import select

        return select(
            up.get("select_coding_result") or {},
            up.get("validate_evidence_coding") or {},
        )
    if atom == "finalize_coding_result":
        from lokay.proc.finalize_coding_result import finalize_result

        return finalize_result(
            up.get("select_coding_result") or {}, up.get("select_evidence_coding") or {}
        )
    if atom in {"coding_manual", "coding_repair_terminal"}:
        from lokay.proc.coding_terminal import terminal

        source = (
            "finalize_coding_result"
            if atom == "coding_manual"
            else "finalize_local_tests"
        )
        return terminal(
            dict((up.get(source) or {}).get("decision") or {}),
            kind="needs_human" if atom == "coding_manual" else "repair_exhausted",
        )
    if atom in {"select_local_test", "select_local_test_recheck"}:
        from lokay.proc.select_local_test import select

        return select(
            up.get(
                "test_local" if atom == "select_local_test" else "test_local_recheck"
            )
            or {}
        )
    if atom == "finalize_local_tests":
        from lokay.proc.finalize_local_tests import finalize

        return finalize(
            up.get("select_local_test") or {}, up.get("select_local_test_recheck") or {}
        )
    raise AssertionError(atom)
