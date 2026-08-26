"""Native Fala proof for one occupancy-refresh catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_refresh_occupancy_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_occupancy_refresh':v.update(receipts=[{'repo':'a/one','issue':2}],repos=['a/one'])
if a=='occupancy_catalog':v.update(state={})
if a=='persist_occupancy_refresh':v['occupied_repos']=['a/one']
if a=='summarize_occupancy_refresh':v['result']={'occupied_repos':['a/one']}"""
    )
    result = run_graph(tmp_path, body, "occupancy-catalog", path_id="refresh_occupancy")
    order = [
        "prepare_occupancy_refresh",
        "occupancy_catalog",
        "persist_occupancy_refresh",
        "summarize_occupancy_refresh",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert list(statuses) == order
    assert not any(
        name.startswith("select_live_receipt_")
        or name.startswith("inspect_live_receipt_")
        or name.startswith("terminate_closed_issue_worker_")
        or name.startswith("select_occupancy_repo_")
        or name.startswith("list_occupancy_pull_requests_")
        or name.startswith("reduce_occupancy_")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_refresh_occupancy_finishes_without_366_effectors(tmp_path):
    body = base_effector(
        """if a=='prepare_occupancy_refresh':v.update(receipts=[],repos=[])
if a=='occupancy_catalog':v.update(state={})
if a=='persist_occupancy_refresh':v['occupied_repos']=[]
if a=='summarize_occupancy_refresh':v['result']={'occupied_repos':[]}"""
    )
    result = run_graph(tmp_path, body, "occupancy-empty", path_id="refresh_occupancy")
    statuses = result["effector_results"]
    assert len(statuses) == 4
    assert statuses["occupancy_catalog"]["status"] == "succeeded"
    assert statuses["summarize_occupancy_refresh"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64
