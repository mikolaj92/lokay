"""Fala subprocess organ: dispatch one atom per process.

Routing lives in ``lokay.organ.*`` (one job family per module).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fala import sdk
from lokay.atom_runtime import (  # noqa: F401 — tests patch these names
    branch_ahead_of_upstream,
    run_atom_main as _run_atom_main,
)
from lokay.organ.agent import handle_agent
from lokay.organ.child_harvest_boundary import handle_child_harvest
from lokay.organ.coding_boundary import handle_coding_boundary
from lokay.organ.common import (  # noqa: F401
    _conduction_values,
    _issue_no_longer_open,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _test_local_ok,
)
from lokay.organ.conflict_resolution_boundary import handle_conflict_resolution
from lokay.organ.daemon_entry_boundary import handle_daemon_entry
from lokay.organ.factory import handle_factory
from lokay.organ.factory_begin_boundary import handle_factory_begin
from lokay.organ.implement import handle_implement
from lokay.organ.implementation_dispatch_boundary import handle_implementation_dispatch
from lokay.organ.implementation_selection_boundary import (
    handle_implementation_selection,
)
from lokay.organ.inbox_survey_boundary import handle_inbox_survey
from lokay.organ.intake_check_boundary import handle_intake_check
from lokay.organ.issue_split_boundary import handle_issue_split
from lokay.organ.issue_triage_boundary import handle_issue_triage
from lokay.organ.departments_boundary import handle_departments
from lokay.organ.issue_triage_department_boundary import handle_issue_triage_department
from lokay.organ.executor_department_boundary import handle_executor_department
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.organ.issues_boundary import handle_issues
from lokay.organ.lanes import handle_lanes
from lokay.organ.leftover_closeout_boundary import handle_leftover_closeout
from lokay.organ.localize_boundary import handle_localize
from lokay.organ.occupancy_refresh_boundary import handle_occupancy_refresh
from lokay.organ.over_budget_boundary import handle_over_budget
from lokay.organ.pass_plan_boundary import handle_pass_plan
from lokay.organ.plan_issue_boundary import handle_plan_issue
from lokay.organ.pr_closeout_boundary import handle_pr_closeout
from lokay.organ.pr_create_boundary import handle_pr_create
from lokay.organ.pr_finalize import handle_pr_finalize
from lokay.organ.pr_outcome import handle_pr_outcome
from lokay.organ.pr_survey_boundary import handle_pr_survey
from lokay.organ.product_budget_boundary import handle_product_budget
from lokay.organ.product_entry_boundary import handle_product_entry
from lokay.organ.publication import handle_publication
from lokay.organ.queue_conflict_boundary import handle_queue_conflict
from lokay.organ.ready_hygiene_boundary import handle_ready_hygiene
from lokay.organ.real_diff_boundary import handle_real_diff
from lokay.organ.recovery import handle_recovery
from lokay.organ.relocalize_boundary import handle_relocalize
from lokay.organ.repair_boundary import handle_repair_boundary
from lokay.organ.review_boundary import handle_review_boundary
from lokay.organ.self_repair import handle_self_repair
from lokay.organ.self_repair_activate_boundary import handle_self_repair_activate
from lokay.organ.self_repair_entry_boundary import handle_self_repair_entry
from lokay.organ.self_repair_prepare_boundary import handle_self_repair_prepare
from lokay.organ.self_repair_validate_boundary import handle_self_repair_validate
from lokay.organ.stage_label_boundary import handle_stage_label
from lokay.organ.stale_implementing_boundary import handle_stale_implementing
from lokay.organ.stale_worktree_boundary import handle_stale_worktree
from lokay.organ.status_boundary import handle_status
from lokay.organ.survey_ready_boundary import handle_survey_ready
from lokay.organ.test_local_boundary import handle_test_local
from lokay.organ.triage_dispatch_boundary import handle_triage_dispatch

_MUTATING_ATOMS = frozenset(
    {
        "run_agent",
        "repair_agent",
        "coding_retry_agent",
        "evidence_coding_agent",
        "pr_repair_retry_agent",
        "evidence_repair_agent",
        "pr_test_repair_agent",
        "issue_to_pr_subflow",
        "coding_execution",
        "local_repair_execution",
        "close_existing_delivery",
        "stale_worktree_catalog",
        "launch_issue_to_pr",
        "label_blocked_dispatch",
        "remove_queue_ready_label",
        "add_queue_tracker_label",
        "park_plan_only_dispatch",
        "commit_all",
        "commit_implementation",
        "commit_repair",
        "push",
        "pr_create",
        "pr_merge",
        "apply_issue_ready",
        "apply_issue_close",
        "apply_issue_mark",
        "apply_issue_manual",
        "create_issue_split_child_1",
        "create_issue_split_child_2",
        "create_issue_split_child_3",
        "create_issue_split_child_4",
        "create_issue_split_child_5",
        "mark_issue_tracker",
        "comment_issue_tracker",
        "close_issue_tracker",
    }
)


def _handle(
    atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    from lokay.organ.common import _cfg_flags, _live_flags

    ctx = {
        "cfg": _cfg_flags(inputs),
        "live": _live_flags(inputs),
        "repo": str(
            inputs.get("repo")
            or up.get("get_issue", {}).get("issue", {}).get("repo")
            or ""
        ),
        "issue_number": None,
        "pr_number": None,
        "repair_mode": str(inputs.get("mode") or "") == "repair",
        "branch": str(
            inputs.get("branch")
            or up.get("make_branch", {}).get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        ),
        "run_atom_main": _run_atom_main,
        "branch_ahead_of_upstream": branch_ahead_of_upstream,
    }
    issue_number = inputs.get("issue") or inputs.get("issue_number")
    if issue_number is None and "get_issue" in up:
        issue_number = up["get_issue"].get("issue", {}).get("number")
    ctx["issue_number"] = int(issue_number) if issue_number is not None else None
    pr_number = inputs.get("pr") or inputs.get("pr_number")
    ctx["pr_number"] = int(pr_number) if pr_number is not None else None

    # The organ is the single mutation boundary.  Re-view live before every
    # mutating atom so a close after get_issue conduction cannot reach a proc.
    if atom in _MUTATING_ATOMS and ctx["issue_number"] is not None:
        from lokay.proc import get_issue

        refused = _issue_no_longer_open(
            up,
            cfg=ctx["cfg"],
            live=ctx["live"],
            repo=ctx["repo"],
            issue_number=ctx["issue_number"],
            run=_run_atom_main,
            get_issue_main=get_issue.main,
        )
        if refused is not None:
            refused.setdefault("issue", ctx["issue_number"])
            refused.setdefault("repo", ctx["repo"])
            return refused

    for handler in (
        handle_recovery,
        handle_factory,
        handle_departments,
        handle_issue_triage_department,
        handle_executor_department,
        handle_pr_triage_department,
        handle_self_repair,
        handle_stale_worktree,
        handle_survey_ready,
        handle_triage_dispatch,
        handle_review_boundary,
        handle_coding_boundary,
        handle_child_harvest,
        handle_conflict_resolution,
        handle_repair_boundary,
        handle_issue_split,
        handle_implementation_dispatch,
        handle_implementation_selection,
        handle_issues,
        handle_issue_triage,
        handle_pr_outcome,
        handle_lanes,
        handle_implement,
        handle_agent,
        handle_publication,
        handle_queue_conflict,
        handle_pr_finalize,
        handle_pass_plan,
        handle_occupancy_refresh,
        handle_stale_implementing,
        handle_over_budget,
        handle_self_repair_prepare,
        handle_self_repair_validate,
        handle_self_repair_activate,
        handle_inbox_survey,
        handle_pr_closeout,
        handle_pr_survey,
        handle_ready_hygiene,
        handle_product_budget,
        handle_product_entry,
        handle_test_local,
        handle_leftover_closeout,
        handle_factory_begin,
        handle_localize,
        handle_relocalize,
        handle_status,
        handle_pr_create,
        handle_stage_label,
        handle_plan_issue,
        handle_intake_check,
        handle_daemon_entry,
        handle_self_repair_entry,
        handle_real_diff,
    ):
        result = handler(atom, inputs, up, ctx)
        if result is not None:
            return result
    raise ValueError(f"unknown atom: {atom!r}")


def _ensure_project_cwd() -> None:
    """Atoms must not inherit Fala's sqlite.fire dylib cwd."""
    root = os.environ.get("LOKAY_ROOT")
    if root and os.path.isdir(root):
        os.chdir(root)
        return
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd()):
        if (candidate / "pyproject.toml").is_file() and (candidate / "fala").is_dir():
            os.chdir(candidate)
            return


def main() -> int:
    _ensure_project_cwd()

    def handler(manifest: dict[str, Any]) -> dict[str, Any]:
        config = sdk.config(manifest)
        atom = str(config.get("atom") or manifest.get("process_id") or "")
        if not atom:
            raise RuntimeError("config.atom is required")
        if atom == "commit_all" and not os.environ.get("LOKAY_HEALTH_LEASE_PATH"):
            raise RuntimeError("health lease path missing at Fala mutation boundary")
        inputs = dict(sdk.declared_inputs(manifest))
        for key, value in sdk.input_values(manifest).items():
            if key not in sdk.INJECTED_INPUT_KEYS and key not in inputs:
                inputs[key] = value
        for key, value in config.items():
            if key == "atom":
                continue
            inputs.setdefault(key, value)
        up = _conduction_values(manifest)
        result = _handle(atom, inputs, up)
        ok_flag = bool(result.get("ok", False)) and result.get("_exit", 0) == 0
        if result.get("status") == "failed":
            ok_flag = False
        if not ok_flag and not result.get("skipped"):
            values = {
                "ok": False,
                "atom": atom,
                **{k: v for k, v in result.items() if k != "_exit"},
            }
            raise RuntimeError(json.dumps(values, ensure_ascii=False)[:2000])
        values = {
            "ok": True,
            "atom": atom,
            **{k: v for k, v in result.items() if k != "_exit"},
        }
        return sdk.output(values=values)

    return sdk.run_manifest_effector(handler)


if __name__ == "__main__":
    raise SystemExit(main())
