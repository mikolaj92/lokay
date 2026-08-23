"""Native Fala proof for bounded detached-worker budget slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_empty_receipts_skip_physical_effects(tmp_path):
    body = base_effector(
        """if a=='prepare_over_budget_reap':v.update(receipts=[],budget_s=480)
if a.startswith('select_budget_receipt_'):v['route']='empty'
if a.startswith('select_budget_') or a.startswith('select_plan_only_') or a.startswith('record_budget_slot_outcome_'):v.update(route='empty',reason='none')
if a=='reduce_over_budget_reap':v.update(reaped=[],kept=[],reaped_count=0,budget_s=480)
if a=='summarize_over_budget_reap':v['result']={'reaped_count':0}"""
    )
    result = run_graph(tmp_path, body, "budget-empty", path_id="reap_over_budget")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["inspect_budget_issue_state_1"] == "skipped"
        and status["commit_over_budget_diff_1"] == "skipped"
        and status["terminate_over_budget_worker_1"] == "skipped"
        and status["summarize_over_budget_reap"] == "succeeded"
    )
