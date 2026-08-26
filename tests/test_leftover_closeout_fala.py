"""Native Fala proof for one leftover-closeout catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_leftover_closeout_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_leftover_closeout':v.update(route='probe',repos=['o/r'],labels=['work:ready','ai:ready'])
if a=='leftover_catalog':v.update(leftover_closed=1)
if a=='update_leftover_stamp':v['result']={'leftover_closed':1}"""
    )
    result = run_graph(tmp_path, body, "leftover-catalog", path_id="leftover_closeout")
    order = [
        "prepare_leftover_closeout",
        "leftover_catalog",
        "update_leftover_stamp",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert list(statuses) == order
    assert not any(
        name.startswith("select_leftover_")
        or name.startswith("list_leftover_")
        or name.startswith("classify_leftover_")
        or name.startswith("record_leftover_")
        or name.startswith("park_leftover_")
        or name.startswith("reduce_leftover_")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_leftover_closeout_finishes_without_394_effectors(tmp_path):
    body = base_effector(
        """if a=='prepare_leftover_closeout':v.update(route='skip',repos=['o/r'],labels=['work:ready'])
if a=='leftover_catalog':v.update(skipped=True,reason='recent_empty')
if a=='update_leftover_stamp':v['result']={'skipped':True}"""
    )
    result = run_graph(tmp_path, body, "leftover-skip", path_id="leftover_closeout")
    statuses = result["effector_results"]
    assert len(statuses) == 3
    assert statuses["leftover_catalog"]["status"] == "succeeded"
    assert statuses["update_leftover_stamp"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64


def test_leftover_catalog_overflow_skips_and_stamps(tmp_path):
    body = base_effector(
        """if a=='prepare_leftover_closeout':v.update(route='probe',repos=['o/r'],ok=True)
if a=='leftover_catalog':v.update(ok=True,route='skip',skipped=True,reason='candidates_exceed_slots')
if a=='update_leftover_stamp':v['result']={'skipped':True,'reason':'candidates_exceed_slots'}"""
    )
    result = run_graph(tmp_path, body, "leftover-overflow", path_id="leftover_closeout")
    statuses = result["effector_results"]
    assert statuses["leftover_catalog"]["status"] == "succeeded"
    assert statuses["update_leftover_stamp"]["status"] == "succeeded"
    assert "recovery_mill" not in statuses
