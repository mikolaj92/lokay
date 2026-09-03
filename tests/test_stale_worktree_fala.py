"""Native Fala proof for one stale-worktree catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_stale_worktree_reap_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='collect_stale_worktree_candidates':v.update(candidate_1={'present':True},candidate_2={'present':False},receipt_safe=True)
if a=='stale_worktree_catalog':v.update(effects=[{'applied':True,'row':{'kept':True}}])
if a=='summarize_stale_worktree_reap':v['result']={'kept_count':1,'reaped_count':0}"""
    )
    result = run_graph(tmp_path, body, "stale-catalog", path_id="stale_worktree_reap")
    order = [
        "collect_stale_worktree_candidates",
        "stale_worktree_catalog",
        "summarize_stale_worktree_reap",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("classify_stale_worktree_")
        or name.startswith("keep_stale_worktree_")
        or name.startswith("remove_stale_worktree_")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_stale_worktree_reap_finishes_without_14_effectors(tmp_path):
    body = base_effector(
        """if a=='collect_stale_worktree_candidates':v.update(receipt_safe=True,deferred=[])
if a=='stale_worktree_catalog':v.update(effects=[])
if a=='summarize_stale_worktree_reap':v['result']={'kept_count':0,'reaped_count':0}"""
    )
    result = run_graph(tmp_path, body, "stale-empty", path_id="stale_worktree_reap")
    statuses = result["effector_results"]
    assert len(statuses) == 3
    assert statuses["stale_worktree_catalog"]["status"] == "succeeded"
    assert statuses["summarize_stale_worktree_reap"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64


def test_stale_worktree_reap_overflow_bound_succeeds(tmp_path):
    body = base_effector(
        """if a=='collect_stale_worktree_candidates':v.update(receipt_safe=True,deferred=[{'present':True}])
if a=='stale_worktree_catalog':v.update(bounded=True,present_count=5,slot_count=4,effects=[{'applied':True,'row':{'removed':True,'reclaimed':True}}])
if a=='summarize_stale_worktree_reap':v['result']={'bounded':True,'reaped_count':1,'archives':{'pruned_count':0}}"""
    )
    result = run_graph(tmp_path, body, "stale-overflow", path_id="stale_worktree_reap")
    statuses = result["effector_results"]
    assert set(statuses) == {
        "collect_stale_worktree_candidates",
        "stale_worktree_catalog",
        "summarize_stale_worktree_reap",
    }
    assert all(row["status"] == "succeeded" for row in statuses.values())
    assert not any(
        name.startswith("prepare_leftover_")
        or name.startswith("leftover_")
        or name.startswith("classify_stale_worktree_")
        or name.startswith("keep_stale_worktree_")
        or name.startswith("remove_stale_worktree_")
        for name in statuses
    )
