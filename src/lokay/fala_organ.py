"""Fala subprocess organ: dispatch one atom per process.

Routing lives in ``lokay.organ.*`` (one job family per module).
"""

from __future__ import annotations

import hashlib
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
from lokay.organ.acceptance_boundary import handle_acceptance
from lokay.organ.child_harvest_boundary import handle_child_harvest
from lokay.organ.coding_boundary import handle_coding_boundary
from lokay.organ.common import (  # noqa: F401
    _conduction_values,
    _issue_no_longer_open,
    _pr_already_merged,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _test_local_ok,
)
from lokay.organ.daemon_entry_boundary import handle_daemon_entry
from lokay.organ.factory import handle_factory
from lokay.organ.factory_begin_boundary import handle_factory_begin
from lokay.organ.implement import handle_implement
from lokay.organ.implementation_dispatch_boundary import handle_implementation_dispatch
from lokay.organ.implementation_selection_boundary import (
    handle_implementation_selection,
)
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
from lokay.organ.map_repo import handle_map_repo
from lokay.organ.plan_issue_boundary import handle_plan_issue
from lokay.organ.pr_closeout_boundary import handle_pr_closeout
from lokay.organ.pr_create_boundary import handle_pr_create
from lokay.organ.pr_finalize import handle_pr_finalize
from lokay.organ.pr_outcome import handle_pr_outcome
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
from lokay.organ.stale_worktree_boundary import handle_stale_worktree
from lokay.organ.status_boundary import handle_status
from lokay.organ.test_local_boundary import handle_test_local
from lokay.organ.triage_dispatch_boundary import handle_triage_dispatch
from lokay.atom_bindings import Binding, BindingError, resolve

_MUTATING_ATOMS = frozenset(
    {
        "run_agent",
        "repair_agent",
        "coding_retry_agent",
        "local_repair_retry_agent",
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


ORGAN_BINDINGS: tuple[Binding, ...] = (
    Binding('finalize_acceptance', handle_acceptance),
    Binding('prepare_acceptance', handle_acceptance),
    Binding('verify_acceptance', handle_acceptance),
    Binding('verify_acceptance_recheck', handle_acceptance),
    Binding('repair_agent', handle_agent),
    Binding('run_agent', handle_agent),
    Binding('child_harvest_terminal', handle_child_harvest),
    Binding('clear_harvest_closed_rows', handle_child_harvest),
    Binding('clear_harvest_cycle_starts', handle_child_harvest),
    Binding('collect_child_harvest_facts', handle_child_harvest),
    Binding('drop_harvest_out_of_scope', handle_child_harvest),
    Binding('harvest_catalog', handle_child_harvest),
    Binding('reconcile_dead_child_receipts', handle_child_harvest),
    Binding('reconcile_harvest_blocked_misses', handle_child_harvest),
    Binding('reconcile_harvest_deliveries', handle_child_harvest),
    Binding('reconcile_harvest_journal_misses', handle_child_harvest),
    Binding('close_existing_delivery', handle_coding_boundary),
    Binding('coding_execution', handle_coding_boundary),
    Binding('coding_execution_terminal', handle_coding_boundary),
    Binding('coding_fail_closed', handle_coding_boundary),
    Binding('coding_repair_terminal', handle_coding_boundary),
    Binding('coding_retry_agent', handle_coding_boundary),
    Binding('collect_coding_issue_snapshot', handle_coding_boundary),
    Binding('collect_coding_localized_diff', handle_coding_boundary),
    Binding('collect_coding_repo_structure', handle_coding_boundary),
    Binding('collect_coding_test_contract', handle_coding_boundary),
    Binding('collect_existing_delivery_pr', handle_coding_boundary),
    Binding('collect_resumed_source', handle_coding_boundary),
    Binding('evidence_coding_agent', handle_coding_boundary),
    Binding('finalize_coding_result', handle_coding_boundary),
    Binding('finalize_local_tests', handle_coding_boundary),
    Binding('issue_to_pr_no_effect', handle_coding_boundary),
    Binding('issue_to_pr_subflow', handle_coding_boundary),
    Binding('local_repair_execution', handle_coding_boundary),
    Binding('local_repair_retry_agent', handle_coding_boundary),
    Binding('local_repair_terminal', handle_coding_boundary),
    Binding('prepare_coding_request', handle_coding_boundary),
    Binding('prepare_local_repair_request', handle_coding_boundary),
    Binding('resolve_existing_delivery', handle_coding_boundary),
    Binding('resolve_implementation_issue', handle_coding_boundary),
    Binding('select_coding_result', handle_coding_boundary),
    Binding('select_evidence_coding', handle_coding_boundary),
    Binding('select_local_test', handle_coding_boundary),
    Binding('select_local_test_recheck', handle_coding_boundary),
    Binding('select_repair_result', handle_coding_boundary),
    Binding('summarize_issue_delivery', handle_coding_boundary),
    Binding('summarize_issue_to_pr', handle_coding_boundary),
    Binding('validate_coding_result', handle_coding_boundary),
    Binding('validate_coding_retry', handle_coding_boundary),
    Binding('validate_evidence_coding', handle_coding_boundary),
    Binding('validate_local_repair_retry', handle_coding_boundary),
    Binding('validate_repair_result', handle_coding_boundary),
    Binding('classify_daemon_preflight', handle_daemon_entry),
    Binding('daemon_entry_terminal', handle_daemon_entry),
    Binding('run_daemon_product_cycle', handle_daemon_entry),
    Binding('run_initial_self_repair', handle_daemon_entry),
    Binding('invoke_self_repair', handle_departments),
    Binding('open_self_repair_incident', handle_departments),
    Binding('run_executor_department', handle_departments),
    Binding('run_issue_triage_department', handle_departments),
    Binding('run_pr_repair_department', handle_departments),
    Binding('run_pr_triage_department', handle_departments),
    Binding('run_self_repair_department', handle_departments),
    Binding('select_executor_department', handle_departments),
    Binding('select_issue_triage_department', handle_departments),
    Binding('select_pr_repair_department', handle_departments),
    Binding('select_pr_triage_department', handle_departments),
    Binding('select_self_repair_department', handle_departments),
    Binding('prepare_executor_rows', handle_executor_department),
    Binding('run_executor_rows', handle_executor_department),
    Binding('select_executor_result', handle_executor_department),
    Binding('select_issue_do_row', handle_executor_department),
    Binding('summarize_executor_department', handle_executor_department),
    Binding('summarize_executor_row', handle_executor_department),
    Binding('compact_state', handle_factory),
    Binding('compute_health', handle_factory),
    Binding('dispatch_implement', handle_factory),
    Binding('dispatch_triage', handle_factory),
    Binding('factory_begin', handle_factory),
    Binding('factory_begin_host_gate', handle_factory),
    Binding('factory_pass_terminal', handle_factory),
    Binding('factory_tick', handle_factory),
    Binding('harvest_factory_children', handle_factory),
    Binding('host_ff', handle_factory),
    Binding('queue_conflict', handle_factory),
    Binding('ready_hygiene', handle_factory),
    Binding('reap_stale_worktrees', handle_factory),
    Binding('record_pass', handle_factory),
    Binding('select_implement', handle_factory),
    Binding('attach_factory_stuck', handle_factory_begin),
    Binding('build_factory_begin_state', handle_factory_begin),
    Binding('build_factory_working_state', handle_factory_begin),
    Binding('classify_leftover_remaining', handle_factory_begin),
    Binding('create_factory_pass_dir', handle_factory_begin),
    Binding('load_factory_config', handle_factory_begin),
    Binding('merge_leftover_remaining', handle_factory_begin),
    Binding('persist_factory_begin_state', handle_factory_begin),
    Binding('persist_factory_tick', handle_factory_begin),
    Binding('persist_factory_working_state', handle_factory_begin),
    Binding('probe_factory_host', handle_factory_begin),
    Binding('read_factory_stuck', handle_factory_begin),
    Binding('seed_factory_occupancy', handle_factory_begin),
    Binding('select_factory_scope', handle_factory_begin),
    Binding('assign_issue', handle_implement),
    Binding('cycle_end', handle_implement),
    Binding('cycle_start', handle_implement),
    Binding('localize', handle_implement),
    Binding('make_branch', handle_implement),
    Binding('pi_budget', handle_implement),
    Binding('plan_issue', handle_implement),
    Binding('relocalize_off_goal', handle_implement),
    Binding('worktree_add', handle_implement),
    Binding('drop_stale_implementation_candidate', handle_implementation_dispatch),
    Binding('inspect_implementation_mutex', handle_implementation_dispatch),
    Binding('keep_busy_launch', handle_implementation_dispatch),
    Binding('keep_implementation_candidate', handle_implementation_dispatch),
    Binding('label_blocked_dispatch', handle_implementation_dispatch),
    Binding('launch_issue_to_pr', handle_implementation_dispatch),
    Binding('park_plan_only_dispatch', handle_implementation_dispatch),
    Binding('persist_blocked_dispatch', handle_implementation_dispatch),
    Binding('persist_dispatch_stuck', handle_implementation_dispatch),
    Binding('record_dispatch_failure', handle_implementation_dispatch),
    Binding('record_dispatch_success', handle_implementation_dispatch),
    Binding('select_blocked_dispatch', handle_implementation_dispatch),
    Binding('select_dispatch_outcome', handle_implementation_dispatch),
    Binding('select_implementation_candidate', handle_implementation_dispatch),
    Binding('select_launch_route', handle_implementation_dispatch),
    Binding('select_mutex_outcome', handle_implementation_dispatch),
    Binding('select_ready_outcome', handle_implementation_dispatch),
    Binding('summarize_implementation_dispatch', handle_implementation_dispatch),
    Binding('verify_selected_issue_ready', handle_implementation_dispatch),
    Binding('write_dispatch_receipt', handle_implementation_dispatch),
    Binding('implementation_selection_catalog', handle_implementation_selection),
    Binding('persist_implementation_selection', handle_implementation_selection),
    Binding('prepare_implementation_selection', handle_implementation_selection),
    Binding('summarize_implementation_selection', handle_implementation_selection),
    Binding('classify_intake_check_route', handle_intake_check),
    Binding('intake_check_terminal', handle_intake_check),
    Binding('parse_intake_covering_prs', handle_intake_check),
    Binding('prepare_intake_check', handle_intake_check),
    Binding('probe_intake_check_shape', handle_intake_check),
    Binding('read_intake_check_issue', handle_intake_check),
    Binding('resolve_intake_check_clone', handle_intake_check),
    Binding('run_intake_ambiguity_check', handle_intake_check),
    Binding('run_intake_duplicate_pr_check', handle_intake_check),
    Binding('run_intake_open_check', handle_intake_check),
    Binding('run_intake_satisfied_check', handle_intake_check),
    Binding('run_intake_shape_check', handle_intake_check),
    Binding('run_intake_superseded_check', handle_intake_check),
    Binding('select_intake_check_result', handle_intake_check),
    Binding('close_issue_tracker', handle_issue_split),
    Binding('comment_issue_tracker', handle_issue_split),
    Binding('mark_issue_tracker', handle_issue_split),
    Binding('plan_issue_split', handle_issue_split),
    Binding('summarize_issue_split', handle_issue_split),
    Binding('apply_issue_blocked', handle_issue_triage),
    Binding('apply_issue_close', handle_issue_triage),
    Binding('apply_issue_manual', handle_issue_triage),
    Binding('apply_issue_mark', handle_issue_triage),
    Binding('apply_issue_ready', handle_issue_triage),
    Binding('apply_issue_skip', handle_issue_triage),
    Binding('collect_issue_covering_prs', handle_issue_triage),
    Binding('collect_issue_linked_prs', handle_issue_triage),
    Binding('collect_issue_named_paths', handle_issue_triage),
    Binding('collect_issue_repo_shape', handle_issue_triage),
    Binding('finalize_issue_triage', handle_issue_triage),
    Binding('issue_evidence_agent', handle_issue_triage),
    Binding('issue_triage_agent', handle_issue_triage),
    Binding('issue_triage_retry_agent', handle_issue_triage),
    Binding('resolve_issue_candidate', handle_issue_triage),
    Binding('resolve_issue_hard_facts', handle_issue_triage),
    Binding('select_issue_evidence', handle_issue_triage),
    Binding('select_issue_triage', handle_issue_triage),
    Binding('select_park_stop', handle_issue_triage),
    Binding('select_triage_leaf', handle_issue_triage),
    Binding('summarize_issue_triage', handle_issue_triage),
    Binding('validate_issue_evidence', handle_issue_triage),
    Binding('validate_issue_triage', handle_issue_triage),
    Binding('validate_issue_triage_retry', handle_issue_triage),
    Binding('verify_issue_evidence', handle_issue_triage),
    Binding('prepare_issue_sieve', handle_issue_triage_department),
    Binding('run_issue_sieve_rows', handle_issue_triage_department),
    Binding('run_issue_sieve_split', handle_issue_triage_department),
    Binding('select_issue_sieve', handle_issue_triage_department),
    Binding('select_issue_sieve_result', handle_issue_triage_department),
    Binding('summarize_issue_sieve_row', handle_issue_triage_department),
    Binding('summarize_issue_triage_department', handle_issue_triage_department),
    Binding('issues_launch_pr', handle_issues),
    Binding('issues_run_triage', handle_issues),
    Binding('list_open_issues', handle_issues),
    Binding('select_issue_executor', handle_issues),
    Binding('select_next_issue', handle_issues),
    Binding('close_issue', handle_lanes),
    Binding('get_issue', handle_lanes),
    Binding('pr_checks', handle_lanes),
    Binding('pr_merge', handle_lanes),
    Binding('publish_delivery_receipt', handle_lanes),
    Binding('stage_label', handle_lanes),
    Binding('leftover_catalog', handle_leftover_closeout),
    Binding('prepare_leftover_closeout', handle_leftover_closeout),
    Binding('update_leftover_stamp', handle_leftover_closeout),
    Binding('build_deterministic_localization', handle_localize),
    Binding('build_explicit_localization', handle_localize),
    Binding('build_localization_agent_request', handle_localize),
    Binding('build_localization_retry', handle_localize),
    Binding('classify_localization_route', handle_localize),
    Binding('inspect_existing_localization', handle_localize),
    Binding('localization_terminal', handle_localize),
    Binding('prepare_localization_request', handle_localize),
    Binding('retry_localization_agent', handle_localize),
    Binding('run_localization_agent', handle_localize),
    Binding('select_localization_candidate', handle_localize),
    Binding('validate_localization_agent_json', handle_localize),
    Binding('validate_localization_paths', handle_localize),
    Binding('validate_localization_retry_json', handle_localize),
    Binding('write_localization_evidence', handle_localize),
    Binding('map_repo', handle_map_repo),
    Binding('authorize_issue_plan_write', handle_plan_issue),
    Binding('build_issue_approach', handle_plan_issue),
    Binding('issue_plan_terminal', handle_plan_issue),
    Binding('prepare_issue_plan_request', handle_plan_issue),
    Binding('record_issue_approach_write', handle_plan_issue),
    Binding('write_issue_approach', handle_plan_issue),
    Binding('authorize_closeout_repair', handle_pr_closeout),
    Binding('authorize_closeout_review_repair', handle_pr_closeout),
    Binding('build_closeout_evidence', handle_pr_closeout),
    Binding('classify_closeout_gate', handle_pr_closeout),
    Binding('classify_closeout_triage', handle_pr_closeout),
    Binding('finalize_closeout_pr', handle_pr_closeout),
    Binding('inspect_closeout_pr', handle_pr_closeout),
    Binding('park_closed_pr_issue', handle_pr_closeout),
    Binding('park_delivered_pr_issue', handle_pr_closeout),
    Binding('read_closeout_checks', handle_pr_closeout),
    Binding('read_closeout_issue', handle_pr_closeout),
    Binding('route_closeout_checks', handle_pr_closeout),
    Binding('run_closeout_repair', handle_pr_closeout),
    Binding('run_closeout_review_repair', handle_pr_closeout),
    Binding('run_closeout_triage', handle_pr_closeout),
    Binding('select_closeout_park_result', handle_pr_closeout),
    Binding('select_closeout_repair_result', handle_pr_closeout),
    Binding('summarize_closeout_pr', handle_pr_closeout),
    Binding('classify_pr_create_issue', handle_pr_create),
    Binding('create_pull_request_effect', handle_pr_create),
    Binding('find_existing_delivery_pr', handle_pr_create),
    Binding('pr_create_terminal', handle_pr_create),
    Binding('prepare_pr_create_request', handle_pr_create),
    Binding('read_pr_create_issue', handle_pr_create),
    Binding('record_existing_delivery_pr', handle_pr_create),
    Binding('list_prs', handle_pr_finalize),
    Binding('pr_label', handle_pr_finalize),
    Binding('classify_pr_triage_checks', handle_pr_outcome),
    Binding('pr_repair_verdict', handle_pr_outcome),
    Binding('review_manual', handle_pr_outcome),
    Binding('review_repair_gate', handle_pr_outcome),
    Binding('review_repair_manual', handle_pr_outcome),
    Binding('select_pr_triage_outcome', handle_pr_outcome),
    Binding('summarize_pr_triage', handle_pr_outcome),
    Binding('list_pr_sieve', handle_pr_triage_department),
    Binding('run_pr_sieve', handle_pr_triage_department),
    Binding('select_pr_sieve', handle_pr_triage_department),
    Binding('select_pr_triage_verdict', handle_pr_triage_department),
    Binding('summarize_pr_triage_department', handle_pr_triage_department),
    Binding('prepare_product_budget', handle_product_budget),
    Binding('select_product_budget_result', handle_product_budget),
    Binding('classify_product_entry_preflight', handle_product_entry),
    Binding('product_entry_terminal', handle_product_entry),
    Binding('run_product_entry_budget', handle_product_entry),
    Binding('assert_real_diff', handle_publication),
    Binding('assert_stamps_committed', handle_publication),
    Binding('commit_all', handle_publication),
    Binding('commit_stamp_files', handle_publication),
    Binding('list_dirty_stamp_paths', handle_publication),
    Binding('local_verification_terminal', handle_publication),
    Binding('pr_create', handle_publication),
    Binding('push', handle_publication),
    Binding('rebase_onto_base', handle_publication),
    Binding('select_publish_gate', handle_publication),
    Binding('test_local', handle_publication),
    Binding('test_local_execution', handle_publication),
    Binding('add_queue_tracker_label', handle_queue_conflict),
    Binding('advance_implementation_selection', handle_queue_conflict),
    Binding('check_queue_covering_pr', handle_queue_conflict),
    Binding('queue_conflict_agent', handle_queue_conflict),
    Binding('queue_conflict_retry_agent', handle_queue_conflict),
    Binding('record_queue_conflict', handle_queue_conflict),
    Binding('remove_queue_ready_label', handle_queue_conflict),
    Binding('select_queue_conflict_candidate', handle_queue_conflict),
    Binding('select_queue_conflict_gate', handle_queue_conflict),
    Binding('select_queue_conflict_outcome', handle_queue_conflict),
    Binding('select_queue_tracker', handle_queue_conflict),
    Binding('summarize_queue_conflict', handle_queue_conflict),
    Binding('validate_queue_conflict', handle_queue_conflict),
    Binding('validate_queue_conflict_retry', handle_queue_conflict),
    Binding('prepare_ready_hygiene', handle_ready_hygiene),
    Binding('ready_hygiene_catalog', handle_ready_hygiene),
    Binding('update_ready_hygiene_stamp', handle_ready_hygiene),
    Binding('classify_localized_diff_scope', handle_real_diff),
    Binding('classify_real_diff_kind', handle_real_diff),
    Binding('classify_real_diff_progress', handle_real_diff),
    Binding('classify_ticket_scope_extra', handle_real_diff),
    Binding('classify_ticket_scope_presence', handle_real_diff),
    Binding('inspect_real_diff_worktree', handle_real_diff),
    Binding('read_real_diff_issue_scope', handle_real_diff),
    Binding('read_real_diff_localize_scope', handle_real_diff),
    Binding('read_real_diff_paths', handle_real_diff),
    Binding('real_diff_terminal', handle_real_diff),
    Binding('last_pass_moving', handle_recovery),
    Binding('recovery_begin', handle_recovery),
    Binding('recovery_factory', handle_recovery),
    Binding('recovery_incident', handle_recovery),
    Binding('recovery_observe', handle_recovery),
    Binding('recovery_record', handle_recovery),
    Binding('recovery_run_self_repair', handle_recovery),
    Binding('select_repair_route', handle_recovery),
    Binding('summarize_daemon_cycle', handle_recovery),
    Binding('authorize_relocalization_restore', handle_relocalize),
    Binding('build_relocalization_agent_request', handle_relocalize),
    Binding('build_relocalization_retry', handle_relocalize),
    Binding('classify_relocalization_off_goal', handle_relocalize),
    Binding('classify_relocalization_residue', handle_relocalize),
    Binding('inspect_relocalization_evidence', handle_relocalize),
    Binding('read_relocalization_changed_paths', handle_relocalize),
    Binding('read_relocalization_issue_paths', handle_relocalize),
    Binding('record_relocalization_restore', handle_relocalize),
    Binding('relocalization_terminal', handle_relocalize),
    Binding('restore_relocalization_residue', handle_relocalize),
    Binding('retry_relocalization_agent', handle_relocalize),
    Binding('run_relocalization_agent', handle_relocalize),
    Binding('select_relocalization_validation', handle_relocalize),
    Binding('validate_relocalization_agent_json', handle_relocalize),
    Binding('validate_relocalization_approval', handle_relocalize),
    Binding('validate_relocalization_retry_json', handle_relocalize),
    Binding('write_relocalization_evidence', handle_relocalize),
    Binding('admit_pr_repair', handle_repair_boundary),
    Binding('collect_repair_changed_files', handle_repair_boundary),
    Binding('collect_repair_pr_metadata', handle_repair_boundary),
    Binding('collect_repair_review_findings', handle_repair_boundary),
    Binding('collect_repair_test_contract', handle_repair_boundary),
    Binding('evidence_repair_agent', handle_repair_boundary),
    Binding('finalize_repair_result', handle_repair_boundary),
    Binding('finalize_repair_tests', handle_repair_boundary),
    Binding('pr_repair_fail_closed', handle_repair_boundary),
    Binding('pr_repair_retry_agent', handle_repair_boundary),
    Binding('pr_repair_terminal', handle_repair_boundary),
    Binding('pr_test_repair_agent', handle_repair_boundary),
    Binding('probe_pr_state', handle_repair_boundary),
    Binding('select_evidence_repair', handle_repair_boundary),
    Binding('select_initial_repair', handle_repair_boundary),
    Binding('select_repair_test', handle_repair_boundary),
    Binding('select_repair_test_recheck', handle_repair_boundary),
    Binding('select_test_repair_result', handle_repair_boundary),
    Binding('summarize_pr_repair', handle_repair_boundary),
    Binding('validate_evidence_repair', handle_repair_boundary),
    Binding('validate_initial_repair', handle_repair_boundary),
    Binding('validate_repair_retry', handle_repair_boundary),
    Binding('validate_test_repair', handle_repair_boundary),
    Binding('collect_pr_review_evidence', handle_review_boundary),
    Binding('evidence_review_agent', handle_review_boundary),
    Binding('finalize_pr_review', handle_review_boundary),
    Binding('pr_review_agent', handle_review_boundary),
    Binding('pr_review_retry_agent', handle_review_boundary),
    Binding('publish_pr_review', handle_review_boundary),
    Binding('resolve_sha_review', handle_review_boundary),
    Binding('review_evidence_catalog', handle_review_boundary),
    Binding('select_evidence_review', handle_review_boundary),
    Binding('select_pr_review', handle_review_boundary),
    Binding('validate_evidence_review', handle_review_boundary),
    Binding('validate_pr_review', handle_review_boundary),
    Binding('validate_pr_review_retry', handle_review_boundary),
    Binding('self_repair_activate', handle_self_repair),
    Binding('self_repair_close', handle_self_repair),
    Binding('self_repair_commit', handle_self_repair),
    Binding('self_repair_preflight', handle_self_repair),
    Binding('self_repair_prepare', handle_self_repair),
    Binding('self_repair_push_main', handle_self_repair),
    Binding('self_repair_run_agent', handle_self_repair),
    Binding('self_repair_validate', handle_self_repair),
    Binding('summarize_self_repair', handle_self_repair),
    Binding('check_dirty_commit_on_origin', handle_self_repair_activate),
    Binding('check_recovery_ancestor_head', handle_self_repair_activate),
    Binding('check_recovery_ancestor_origin', handle_self_repair_activate),
    Binding('classify_activated_head', handle_self_repair_activate),
    Binding('classify_canonical_checkout', handle_self_repair_activate),
    Binding('fast_forward_recovery_commit', handle_self_repair_activate),
    Binding('fetch_canonical_main', handle_self_repair_activate),
    Binding('prepare_self_repair_activation', handle_self_repair_activate),
    Binding('read_activated_head', handle_self_repair_activate),
    Binding('read_canonical_checkout_status', handle_self_repair_activate),
    Binding('record_canonical_fetch', handle_self_repair_activate),
    Binding('record_recovery_fast_forward', handle_self_repair_activate),
    Binding('record_recovery_head_ancestry', handle_self_repair_activate),
    Binding('self_repair_activation_terminal', handle_self_repair_activate),
    Binding('classify_self_repair_entry', handle_self_repair_entry),
    Binding('classify_self_repair_entry_outcome', handle_self_repair_entry),
    Binding('prepare_self_repair_entry', handle_self_repair_entry),
    Binding('record_authored_self_repair', handle_self_repair_entry),
    Binding('record_self_repair_entry_failure', handle_self_repair_entry),
    Binding('record_self_repair_entry_start', handle_self_repair_entry),
    Binding('record_self_repair_entry_success', handle_self_repair_entry),
    Binding('run_authored_self_repair', handle_self_repair_entry),
    Binding('select_self_repair_entry_result', handle_self_repair_entry),
    Binding('self_repair_entry_terminal', handle_self_repair_entry),
    Binding('write_self_repair_restart_marker', handle_self_repair_entry),
    Binding('check_self_repair_mutation_gate', handle_self_repair_prepare),
    Binding('create_self_repair_worktree', handle_self_repair_prepare),
    Binding('fetch_self_repair_main', handle_self_repair_prepare),
    Binding('find_published_self_repair', handle_self_repair_prepare),
    Binding('inspect_self_repair_ancestry', handle_self_repair_prepare),
    Binding('inspect_self_repair_changes', handle_self_repair_prepare),
    Binding('inspect_self_repair_commit', handle_self_repair_prepare),
    Binding('inspect_self_repair_ownership', handle_self_repair_prepare),
    Binding('read_self_repair_base', handle_self_repair_prepare),
    Binding('remove_self_repair_worktree', handle_self_repair_prepare),
    Binding('resolve_self_repair_checkout', handle_self_repair_prepare),
    Binding('select_self_repair_base_gate', handle_self_repair_prepare),
    Binding('select_self_repair_changes_gate', handle_self_repair_prepare),
    Binding('select_self_repair_commit_gate', handle_self_repair_prepare),
    Binding('select_self_repair_commit_validation_gate', handle_self_repair_prepare),
    Binding('select_self_repair_fetch_gate', handle_self_repair_prepare),
    Binding('select_self_repair_origin_gate', handle_self_repair_prepare),
    Binding('select_self_repair_ownership_gate', handle_self_repair_prepare),
    Binding('select_self_repair_prepare_result', handle_self_repair_prepare),
    Binding('select_self_repair_publish_gate', handle_self_repair_prepare),
    Binding('select_self_repair_remove_outcome', handle_self_repair_prepare),
    Binding('select_self_repair_shape_gate', handle_self_repair_prepare),
    Binding('select_self_repair_worktree_route', handle_self_repair_prepare),
    Binding('summarize_self_repair_prepare', handle_self_repair_prepare),
    Binding('validate_self_repair_change_shape', handle_self_repair_prepare),
    Binding('validate_self_repair_commit', handle_self_repair_prepare),
    Binding('verify_self_repair_origin', handle_self_repair_prepare),
    Binding('check_self_repair_tracked_cached', handle_self_repair_validate),
    Binding('check_self_repair_tracked_committed', handle_self_repair_validate),
    Binding('check_self_repair_tracked_working', handle_self_repair_validate),
    Binding('classify_self_repair_candidate_diff', handle_self_repair_validate),
    Binding('inspect_self_repair_candidate_identity', handle_self_repair_validate),
    Binding('list_self_repair_untracked_paths', handle_self_repair_validate),
    Binding('read_self_repair_candidate_state', handle_self_repair_validate),
    Binding('recheck_self_repair_identity', handle_self_repair_validate),
    Binding('run_self_repair_tests', handle_self_repair_validate),
    Binding('select_self_repair_committed_gate', handle_self_repair_validate),
    Binding('select_self_repair_committed_need', handle_self_repair_validate),
    Binding('select_self_repair_identity_gate', handle_self_repair_validate),
    Binding('self_repair_untracked_catalog', handle_self_repair_validate),
    Binding('summarize_self_repair_validation', handle_self_repair_validate),
    Binding('validate_self_repair_identity_request', handle_self_repair_validate),
    Binding('verify_self_repair_candidate_identity', handle_self_repair_validate),
    Binding('add_stage_labels_effect', handle_stage_label),
    Binding('classify_stage_issue', handle_stage_label),
    Binding('comment_stage_receipt_effect', handle_stage_label),
    Binding('prepare_stage_transition', handle_stage_label),
    Binding('read_stage_issue', handle_stage_label),
    Binding('record_stage_removal', handle_stage_label),
    Binding('remove_stage_labels_effect', handle_stage_label),
    Binding('stage_label_terminal', handle_stage_label),
    Binding('collect_stale_worktree_candidates', handle_stale_worktree),
    Binding('stale_worktree_catalog', handle_stale_worktree),
    Binding('summarize_stale_worktree_reap', handle_stale_worktree),
    Binding('classify_status_readiness', handle_status),
    Binding('describe_status_graphs', handle_status),
    Binding('read_status_clone_facts', handle_status),
    Binding('read_status_config', handle_status),
    Binding('read_status_lease', handle_status),
    Binding('read_status_pass_receipt', handle_status),
    Binding('read_status_repo_locks', handle_status),
    Binding('read_status_work_units', handle_status),
    Binding('record_status_preflight', handle_status),
    Binding('reduce_status_snapshot', handle_status),
    Binding('run_status_preflight', handle_status),
    Binding('status_snapshot_terminal', handle_status),
    Binding('build_test_terminal_cached', handle_test_local),
    Binding('build_test_terminal_green', handle_test_local),
    Binding('build_test_terminal_inspection', handle_test_local),
    Binding('build_test_terminal_red', handle_test_local),
    Binding('classify_test_terminal', handle_test_local),
    Binding('derive_changed_test_scope', handle_test_local),
    Binding('inspect_test_declaration', handle_test_local),
    Binding('read_test_green_cache', handle_test_local),
    Binding('run_changed_scope_tests', handle_test_local),
    Binding('run_declared_tests', handle_test_local),
    Binding('select_declared_test_outcome', handle_test_local),
    Binding('select_green_test_result', handle_test_local),
    Binding('select_test_terminal', handle_test_local),
    Binding('write_test_green_cache', handle_test_local),
    Binding('check_triage_stuck', handle_triage_dispatch),
    Binding('record_triage_dispatch', handle_triage_dispatch),
    Binding('run_issue_triage_subflow', handle_triage_dispatch),
    Binding('select_triage_gate', handle_triage_dispatch),
    Binding('select_triage_run', handle_triage_dispatch),
    Binding('select_triage_target', handle_triage_dispatch),
    Binding('summarize_triage_dispatch', handle_triage_dispatch),
    Binding('select_executor_slot_', handle_executor_department, numbered=True),
    Binding('run_executor_row_', handle_executor_department, numbered=True),
    Binding('classify_executor_row_', handle_executor_department, numbered=True),
    Binding('create_issue_split_child_', handle_issue_split, numbered=True),
    Binding('select_issue_sieve_slot_', handle_issue_triage_department, numbered=True),
    Binding('run_issue_sieve_row_', handle_issue_triage_department, numbered=True),
    Binding('classify_issue_sieve_row_', handle_issue_triage_department, numbered=True),
    Binding('select_product_pass_slot_', handle_product_budget, numbered=True),
    Binding('run_product_factory_pass_', handle_product_budget, numbered=True),
    Binding('run_product_leftover_closeout_', handle_product_budget, numbered=True),
    Binding('apply_product_leftover_', handle_product_budget, numbered=True),
    Binding('record_product_pass_', handle_product_budget, numbered=True),
    Binding('classify_product_pass_', handle_product_budget, numbered=True),
    Binding('classify_product_plateau_', handle_product_budget, numbered=True),
    Binding('decide_product_pass_stop_', handle_product_budget, numbered=True),
    Binding('finalize_product_pass_', handle_product_budget, numbered=True),
)


def _handle(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    *,
    process_id: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from lokay.activity import record_atom_start
    from lokay.organ.common import _cfg_flags, _live_flags

    record_atom_start(atom=atom, inputs=inputs, process_id=process_id)
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

    if atom in _MUTATING_ATOMS and ctx["pr_number"] is not None:
        from lokay.proc import probe_pr_state

        refused = _pr_already_merged(
            up,
            cfg=ctx["cfg"],
            live=ctx["live"],
            repo=ctx["repo"],
            pr_number=ctx["pr_number"],
            run=_run_atom_main,
            probe_main=probe_pr_state.main,
        )
        if refused is not None:
            refused.setdefault("pr", ctx["pr_number"])
            refused.setdefault("repo", ctx["repo"])
            return refused

    binding = resolve(atom, ORGAN_BINDINGS)
    result = binding.handler(atom, inputs, up, ctx)
    if result is None:
        raise BindingError(f"missing atom binding: {atom!r}")
    if provenance is not None:
        from lokay.execution_provenance import implementation_identity

        provenance.update(implementation_identity(binding.handler))
        provenance["binding"] = binding.name
        provenance["attempt"] = str(process_id or "")
    return result


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


def organ_envelope(atom: str, result: dict[str, Any]) -> dict[str, Any]:
    """Keep classified ok=true facts, including agent transport status=failed.

    Adapter failure is ok=false without a classified skip/route. A localize
    fallback with status=failed is still a succeeded organ row.
    """
    skipped = bool(result.get("skipped"))
    classified = str(result.get("route") or "")
    ok_flag = bool(result.get("ok", False)) and result.get("_exit", 0) == 0
    if not ok_flag and not skipped:
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
    if classified:
        values["route"] = classified
    return values


def _fep_request(manifest: dict[str, Any]) -> dict[str, Any]:
    """Create the FEP request represented by Fala's filesystem manifest.

    Fala transports the request to subprocesses as an adapter manifest for
    compatibility with non-Python effectors. The Python organ emits a FEP/1
    result, so it restores the request identity from that transport data.
    """
    request: dict[str, Any] = {
        "protocol": "fala-effector/1",
        "message_kind": "effector.request",
        "run_id": str(os.environ.get("FALA_RUN_ID") or manifest.get("run_id") or "run"),
        "process_id": str(manifest.get("process_id") or ""),
        "execution_id": str(manifest.get("execution_id") or ""),
        "attempt": int(manifest.get("attempt") or 1),
        "impulse_id": str(manifest.get("impulse_id") or "impulse:lokay-organ"),
        "process_fingerprint": "process:lokay-organ",
        "path_digest": "path:lokay-organ",
        "capability": "lokay_atom",
        "input": dict(manifest.get("input") or {}),
        "config": dict(manifest.get("config") or {}),
        "output_contract_ref": "schema:lokay-atom",
    }
    body = json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    request["message_id"] = "msg:sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    return request


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
        provenance: dict[str, Any] = {}
        result = _handle(
            atom,
            inputs,
            up,
            process_id=str(manifest.get("process_id") or "") or None,
            provenance=provenance,
        )
        return sdk.output(
            values=organ_envelope(atom, result),
            metadata={"implementation": provenance},
        )

    return sdk.run_manifest_effector(handler)


if __name__ == "__main__":
    raise SystemExit(main())
