"""Native Fala proofs for catalog and one-PR closeout graphs."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_manual_pr_skips_checks_and_finishes(tmp_path):
    body = base_effector(
        """if a=='inspect_closeout_pr':v.update(route='manual',repo='o/r',pr_number=7,repair_budget=1,policy={})
if a=='read_closeout_issue':v.update(route='open_or_unknown')
if a=='classify_closeout_gate':v.update(route='manual',reason='manual',inspected={'repo':'o/r','pr_number':7,'repair_budget':1},issue_read={})
if a=='route_closeout_checks':v.update(route='final',domain_route='skip')
if a=='classify_closeout_triage':v.update(route='final')
if a.startswith('authorize_closeout_'):v.update(route='skip')
if a=='select_closeout_repair_result':v.update(repair_used=0)
if a=='finalize_closeout_pr':v.update(route='skip',still_open=True,repo='o/r',repair_budget=1)
if a=='summarize_closeout_pr':v['result']={'route':'skip'}"""
    )
    result = run_graph(tmp_path, body, "closeout-manual", path_id="closeout_pr")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["read_closeout_checks"] == "skipped"
        and status["run_closeout_triage"] == "skipped"
        and status["summarize_closeout_pr"] == "succeeded"
    )


def test_closeout_prs_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_closeout':v.update(repos=['o/r'],repair_budget=1)
if a=='closeout_catalog':v['state']={}
if a=='persist_pr_closeout':v.update(remaining_prs=1)
if a=='summarize_pr_closeout':v['result']={'remaining_prs':1}"""
    )
    result = run_graph(tmp_path, body, "closeout-catalog", path_id="closeout_prs")
    order = [
        "prepare_pr_closeout",
        "closeout_catalog",
        "persist_pr_closeout",
        "summarize_pr_closeout",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("select_pr_closeout_slot_")
        or name.startswith("run_pr_closeout_slot_")
        or name.startswith("record_pr_closeout_slot_")
        or name.startswith("reduce_pr_closeout")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_closeout_prs_finishes_without_94_effectors(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_closeout':v.update(repos=[],repair_budget=0)
if a=='closeout_catalog':v['state']={}
if a=='persist_pr_closeout':v.update(remaining_prs=0)
if a=='summarize_pr_closeout':v['result']={'remaining_prs':0}"""
    )
    result = run_graph(tmp_path, body, "closeout-empty", path_id="closeout_prs")
    statuses = result["effector_results"]
    assert len(statuses) == 4
    assert statuses["closeout_catalog"]["status"] == "succeeded"
    assert statuses["summarize_pr_closeout"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64
