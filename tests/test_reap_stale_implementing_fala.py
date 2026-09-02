"""Native Fala proof for one stale-implementing catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_reap_stale_implementing_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_stale_implementing_reap':v.update(route='recent_empty',repos=[])
if a=='stale_implementing_catalog':v.update(reaped=[],reaped_count=0)
if a=='persist_stale_implementing_reap':v.update(reaped=[],reaped_count=0)
if a=='summarize_stale_implementing_reap':v['result']={'skipped':True,'reason':'recent_empty'}"""
    )
    result = run_graph(
        tmp_path, body, "stale-catalog", path_id="reap_stale_implementing"
    )
    order = [
        "prepare_stale_implementing_reap",
        "stale_implementing_catalog",
        "persist_stale_implementing_reap",
        "summarize_stale_implementing_reap",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("select_stale_repo_")
        or name.startswith("list_stale_repo_")
        or name.startswith("reduce_stale_repo_")
        or name.startswith("select_stale_candidate_")
        or name.startswith("restore_stale_issue_ready_")
        or name.startswith("reduce_stale_")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_reap_stale_implementing_finishes_without_277_effectors(tmp_path):
    body = base_effector(
        """if a=='prepare_stale_implementing_reap':v.update(route='probe',repos=['a/one'])
if a=='stale_implementing_catalog':v.update(reaped=[],reaped_count=0)
if a=='persist_stale_implementing_reap':v.update(reaped=[],reaped_count=0)
if a=='summarize_stale_implementing_reap':v['result']={'reaped_count':0}"""
    )
    result = run_graph(tmp_path, body, "stale-probe", path_id="reap_stale_implementing")
    statuses = result["effector_results"]
    assert len(statuses) == 4
    assert statuses["stale_implementing_catalog"]["status"] == "succeeded"
    assert statuses["summarize_stale_implementing_reap"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64
