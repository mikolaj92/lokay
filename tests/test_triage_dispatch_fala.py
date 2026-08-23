"""Native Fala proofs for serial inbox-triage dispatch."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def test_triage_target_runs_subflow_and_records(tmp_path):
    sub = tmp_path / "sub"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='select_triage_target':v.update(route='target',repo='a/b',issue=1)
if a=='check_triage_stuck':v['route']='run'
if a=='select_triage_gate':v['route']='run'
if a=='run_issue_triage_subflow':v.update(route='completed',triage={'ok':True,'applied':True});Path(%r).write_text('ran')
if a=='select_triage_run':v.update(route='completed',triage={'ok':True,'applied':True})
if a=='record_triage_dispatch':v.update(route='done',ran=1)
if a=='summarize_triage_dispatch':v['result']={'ran':1}""" % str(sub)
    )
    r = run_graph(tmp_path, body, "triage-run", path_id="triage_dispatch")
    st = {k: x["status"] for k, x in r["effector_results"].items()}
    assert sub.read_text() == "ran" and st["summarize_triage_dispatch"] == "succeeded"


def test_blocked_target_skips_subflow(tmp_path):
    sub = tmp_path / "sub"
    body = base_effector(
        """if a=='select_triage_target':v.update(route='target',repo='a/b',issue=1)
if a=='check_triage_stuck':v['route']='blocked'
if a=='select_triage_gate':v['route']='blocked'
if a=='run_issue_triage_subflow':Path(%r).write_text('bad')
if a=='select_triage_run':v['route']='blocked'
if a=='record_triage_dispatch':v.update(route='done',ran=0)
if a=='summarize_triage_dispatch':v['result']={'ran':0}""" % str(sub)
    )
    r = run_graph(tmp_path, body, "triage-blocked", path_id="triage_dispatch")
    st = {k: x["status"] for k, x in r["effector_results"].items()}
    assert not sub.exists() and st["run_issue_triage_subflow"] == "skipped"
