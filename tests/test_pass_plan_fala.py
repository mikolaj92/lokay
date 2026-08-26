"""Native Fala proof for one pass-plan catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_plan_pass_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_pass_plan':v.update(repos=['a/one'])
if a=='plan_catalog':v['plan']={'triage_targets':[]}
if a=='persist_pass_plan':v.update(triage_count=0)
if a=='summarize_pass_plan':v['result']={'triage_count':0}"""
    )
    result = run_graph(tmp_path, body, "plan-catalog", path_id="plan_pass")
    order = [
        "prepare_pass_plan",
        "plan_catalog",
        "persist_pass_plan",
        "summarize_pass_plan",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert list(statuses) == order
    assert not any(
        name.startswith("select_plan_repo_")
        or name.startswith("build_repo_plan_fragment_")
        or name.startswith("record_repo_plan_fragment_")
        or name.startswith("reduce_pass_plan")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_plan_pass_small_catalog_finishes_without_64_ticks(tmp_path):
    body = base_effector(
        """if a=='prepare_pass_plan':v.update(repos=['a/one'])
if a=='plan_catalog':v['plan']={'triage_targets':[]}
if a=='persist_pass_plan':v.update(triage_count=0)
if a=='summarize_pass_plan':v['result']={'triage_count':0}"""
    )
    result = run_graph(tmp_path, body, "plan-small", path_id="plan_pass")
    statuses = result["effector_results"]
    assert len(statuses) == 4
    assert statuses["plan_catalog"]["status"] == "succeeded"
    assert statuses["summarize_pass_plan"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64
