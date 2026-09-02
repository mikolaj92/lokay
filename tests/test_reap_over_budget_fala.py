"""Native Fala proof for one over-budget catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_reap_over_budget_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_over_budget_reap':v.update(receipts=[],budget_s=480)
if a=='over_budget_catalog':v.update(reaped=[],kept=[],reaped_count=0,budget_s=480)
if a=='summarize_over_budget_reap':v['result']={'reaped_count':0}"""
    )
    result = run_graph(tmp_path, body, "budget-catalog", path_id="reap_over_budget")
    order = [
        "prepare_over_budget_reap",
        "over_budget_catalog",
        "summarize_over_budget_reap",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("select_budget_receipt_")
        or name.startswith("inspect_budget_")
        or name.startswith("commit_over_budget_")
        or name.startswith("terminate_over_budget_")
        or name.startswith("reduce_over_budget_reap")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16
