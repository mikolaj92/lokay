"""Native Fala proofs for catalog and one-PR closeout graphs."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


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


def test_catalog_runs_one_nested_slot(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_closeout':v.update(repos=['o/r'],repair_budget=1)
if a.startswith('select_pr_closeout_slot_'):v.update(route='closeout' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '',repair_budget=1)
if a.startswith('run_pr_closeout_slot_'):v['result']={'ok':True,'repo':'o/r','still_open':True,'repair_budget':1}
if a.startswith('record_pr_closeout_slot_'):v.update(repo='o/r' if a.endswith('_1') else '',repair_budget=1)
if a=='reduce_pr_closeout':v['state']={}
if a=='persist_pr_closeout':v.update(remaining_prs=1)
if a=='summarize_pr_closeout':v['result']={'remaining_prs':1}"""
    )
    result = run_graph(tmp_path, body, "closeout-catalog", path_id="closeout_prs")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_pr_closeout_slot_1"] == "succeeded"
        and status["run_pr_closeout_slot_2"] == "skipped"
        and status["summarize_pr_closeout"] == "succeeded"
    )
