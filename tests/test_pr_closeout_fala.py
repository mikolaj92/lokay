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


def test_closeout_prs_runs_authored_slots(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_closeout':v.update(ok=True,repos=['o/r'],repair_budget=1)
if a=='select_pr_closeout_slot_1':v.update(route='closeout',slot=1,repo='o/r',pr={'number':7})
if a.startswith('select_pr_closeout_slot_') and a!='select_pr_closeout_slot_1':v.update(route='empty')
if a=='run_pr_closeout_slot_1':v.update(ok=True,result={'still_open':False,'repo':'o/r','progress':1})
if a.startswith('record_pr_closeout_slot_'):v.update(ok=True,repo='o/r')
if a=='reduce_pr_closeout':v.update(ok=True,state={'remaining_prs':0})
if a=='persist_pr_closeout':v.update(remaining_prs=0)
if a=='summarize_pr_closeout':v['result']={'remaining_prs':0}"""
    )
    result = run_graph(tmp_path, body, "closeout-catalog", path_id="closeout_prs")
    statuses = result["effector_results"]
    assert statuses["prepare_pr_closeout"]["status"] == "succeeded"
    assert statuses["select_pr_closeout_slot_1"]["status"] == "succeeded"
    assert statuses["run_pr_closeout_slot_1"]["status"] == "succeeded"
    assert statuses["reduce_pr_closeout"]["status"] == "succeeded"
    assert statuses["persist_pr_closeout"]["status"] == "succeeded"
    assert "closeout_catalog" not in statuses
    assert result.get("ticks_used", 512) <= 512


def test_closeout_prs_skips_empty_slots(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_closeout':v.update(ok=True,repos=[],repair_budget=0)
if a.startswith('select_pr_closeout_slot_'):v.update(route='empty')
if a=='reduce_pr_closeout':v.update(ok=True,state={'remaining_prs':0})
if a=='persist_pr_closeout':v.update(remaining_prs=0)
if a=='summarize_pr_closeout':v['result']={'remaining_prs':0}"""
    )
    result = run_graph(tmp_path, body, "closeout-empty", path_id="closeout_prs")
    statuses = result["effector_results"]
    assert statuses["prepare_pr_closeout"]["status"] == "succeeded"
    assert statuses["run_pr_closeout_slot_1"]["status"] == "skipped"
    assert statuses["summarize_pr_closeout"]["status"] == "succeeded"
    assert "closeout_catalog" not in statuses
