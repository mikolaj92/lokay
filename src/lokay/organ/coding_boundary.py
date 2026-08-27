"""Fala bindings for the explicit issue implementation boundary."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from lokay.config import load_config
from lokay.organ.common import _issue_raw, _worktree_path

_ATOMS = frozenset(
    {
        "prepare_coding_request",
        "coding_execution",
        "coding_execution_terminal",
        "prepare_local_repair_request",
        "local_repair_execution",
        "local_repair_terminal",
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
        "summarize_issue_delivery",
        "summarize_issue_to_pr",
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
    if atom == "prepare_coding_request":
        from lokay.proc.prepare_coding_request import prepare

        return prepare(
            worktree=_worktree_path(up, inputs),
            repo=str(ctx.get("repo") or inputs.get("repo") or ""),
            issue=ctx.get("issue_number")
            if ctx.get("issue_number") is not None
            else inputs.get("issue"),
            issue_raw=_issue_raw(up, inputs),
            localize=dict(inputs.get("localize") or up.get("localize") or {}),
            branch=str(
                (up.get("make_branch") or {}).get("branch")
                or inputs.get("branch")
                or ""
            ),
            live=bool(inputs.get("live")),
        )
    if atom == "coding_execution":
        from lokay.proc.coding_execution_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or inputs.get("config") or "")
            or None,
            live=bool(inputs.get("live")),
            extra_inputs={
                "config_path": inputs.get("config_path") or inputs.get("config") or "",
                "live": bool(inputs.get("live")),
                "worktree": _worktree_path(up, inputs),
                "repo": str(ctx.get("repo") or inputs.get("repo") or ""),
                "issue": ctx.get("issue_number")
                if ctx.get("issue_number") is not None
                else inputs.get("issue"),
                "issue_raw": _issue_raw(up, inputs),
                "localize": dict(up.get("localize") or inputs.get("localize") or {}),
                "branch": str(
                    (up.get("make_branch") or {}).get("branch")
                    or inputs.get("branch")
                    or ""
                ),
            },
        )
    if atom == "coding_execution_terminal":
        from lokay.proc.coding_execution_terminal import terminal

        return terminal(
            up.get("finalize_coding_result") or {},
            up.get("coding_manual") or {},
        )
    if atom == "prepare_local_repair_request":
        from lokay.proc.prepare_local_repair_request import prepare

        return prepare(
            worktree=_worktree_path(up, inputs),
            repo=str(ctx.get("repo") or inputs.get("repo") or ""),
            issue=ctx.get("issue_number")
            if ctx.get("issue_number") is not None
            else inputs.get("issue"),
            issue_raw=_issue_raw(up, inputs),
            branch=str(
                (up.get("make_branch") or {}).get("branch")
                or inputs.get("branch")
                or ""
            ),
            first_test=dict(inputs.get("first_test") or {}),
            live=bool(inputs.get("live")),
        )
    if atom == "local_repair_execution":
        from lokay.proc.local_repair_execution_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or inputs.get("config") or "")
            or None,
            live=bool(inputs.get("live")),
            extra_inputs={
                "config_path": inputs.get("config_path") or inputs.get("config") or "",
                "live": bool(inputs.get("live")),
                "worktree": _worktree_path(up, inputs),
                "repo": str(ctx.get("repo") or inputs.get("repo") or ""),
                "issue": ctx.get("issue_number")
                if ctx.get("issue_number") is not None
                else inputs.get("issue"),
                "issue_raw": _issue_raw(up, inputs),
                "branch": str(
                    (up.get("make_branch") or {}).get("branch")
                    or inputs.get("branch")
                    or ""
                ),
                "first_test": dict(
                    up.get("test_local_execution")
                    or up.get("test_local")
                    or inputs.get("first_test")
                    or {}
                ),
            },
        )
    if atom == "local_repair_terminal":
        from lokay.proc.local_repair_terminal import terminal

        return terminal(
            up.get("select_repair_result") or {},
            up.get("select_local_test_recheck") or {},
        )
    worktree = Path(_worktree_path(up, inputs))
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
    if atom == "summarize_issue_to_pr":
        from lokay.proc.summarize_issue_to_pr import summarize

        return summarize(
            delivery=up.get("issue_to_pr_subflow") or {},
            closeout=up.get("close_existing_delivery") or {},
            no_effect=up.get("issue_to_pr_no_effect") or {},
        )
    if atom == "summarize_issue_delivery":
        from lokay.proc.summarize_issue_delivery import summarize

        return summarize(
            branch=up.get("make_branch") or {},
            pr_create=up.get("pr_create") or {},
            pr_label=up.get("pr_label") or {},
        )
    if atom == "resolve_implementation_issue":
        from lokay.proc.resolve_implementation_issue import resolve

        return resolve(_issue_raw(up, inputs))
    if atom == "select_repair_result":
        from lokay.proc.select_repair_result import select

        return select(
            up.get("validate_repair_result") or {},
            applicable=(up.get("select_local_test") or {}).get("route") == "fail"
            or "prepare_local_repair_request" in up,
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

            return collect(_issue_raw(up, inputs))
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

        source = (
            "test_local_recheck"
            if atom == "select_local_test_recheck"
            else "test_local_execution"
            if "test_local_execution" in up
            else "test_local"
        )
        return select(up.get(source) or {})
    if atom == "finalize_local_tests":
        from lokay.proc.finalize_local_tests import finalize

        return finalize(
            up.get("select_local_test") or {},
            up.get("select_local_test_recheck")
            or up.get("local_repair_execution")
            or {},
        )
    raise AssertionError(atom)
