"""Native Fala proof for explicit receipt and repository occupancy slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_one_open_receipt_and_one_repo(tmp_path):
    body = base_effector(
        """if a=='prepare_occupancy_refresh':v.update(receipts=[{'repo':'a/one','issue':2}],repos=['a/one'])
if a=='clear_merged_dead_receipts':v['cleared']=[]
if a.startswith('select_live_receipt_'):v.update(route='receipt' if a.endswith('_1') else 'empty')
if a.startswith('inspect_live_receipt_issue_'):v.update(route='occupied',repo='a/one',issue=2)
if a.startswith('record_live_receipt_outcome_'):v.update(route='occupied' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a=='reduce_occupancy_facts':v.update(occupied=['a/one'])
if a.startswith('select_occupancy_repo_'):v.update(route='repo' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a.startswith('inspect_repo_pr_refresh_'):v.update(route='occupied',repo='a/one')
if a.startswith('select_repo_pr_refresh_gate_'):v.update(route='occupied' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a.startswith('record_repo_pr_refresh_'):v.update(route='occupied' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a=='reduce_occupancy_refresh':v['state']={}
if a=='persist_occupancy_refresh':v['occupied_repos']=['a/one']
if a=='summarize_occupancy_refresh':v['result']={'occupied_repos':['a/one']}"""
    )
    result = run_graph(tmp_path, body, "occupancy-one", path_id="refresh_occupancy")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["inspect_live_receipt_issue_1"] == "succeeded"
        and status["inspect_live_receipt_issue_2"] == "skipped"
        and status["list_occupancy_pull_requests_1"] == "skipped"
        and status["summarize_occupancy_refresh"] == "succeeded"
    )
