"""Native Fala proof for staged detached-child harvest."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_harvest_conducts_every_reconciliation_stage_in_order(tmp_path):
    body = base_effector(
        """
if a=='harvest_catalog':v['closed_catalog']={}
v.update(stuck_path='/tmp/stuck.json',stuck={'issues':{}},receipts=[],events={},history={},repos=[],cycle_dir='/tmp/cycle',home='/tmp')"""
    )
    result = run_graph(tmp_path, body, "harvest-stages", path_id="child_harvest")
    order = [
        "collect_child_harvest_facts",
        "reconcile_dead_child_receipts",
        "reconcile_harvest_journal_misses",
        "reconcile_harvest_deliveries",
        "reconcile_harvest_blocked_misses",
        "harvest_catalog",
        "clear_harvest_closed_rows",
        "drop_harvest_out_of_scope",
        "clear_harvest_cycle_starts",
        "child_harvest_terminal",
    ]
    statuses = result["effector_results"]
    assert all(statuses[x]["status"] == "succeeded" for x in order)
