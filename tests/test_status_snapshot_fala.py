"""Native Fala proofs for authored read-only status snapshot."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(preflight: bool) -> str:
    return base_effector(
        f"""if a=='read_status_config':v.update(config='c',mode='live',executor_enabled=True,merge_enabled=True,require_checks=True,require_llm_review=True,max_issue_to_pr_per_pass=1,state_path='/tmp/state',repos=[],preflight_requested={preflight!s},full=False)
if a=='classify_status_readiness':v.update(mill_ready=True,blockers=[],policy_notes=[])
if a=='read_status_clone_facts':v['missing_clones']=[]
if a=='read_status_lease':v.update(lease_ok=True,lease_reason='ok')
if a=='read_status_pass_receipt':v['receipt']=None
if a=='read_status_work_units':v['work_units']=[]
if a=='describe_status_graphs':v['graphs']=['factory_pass']
if a=='run_status_preflight':v.update(route='record',preflight={{'ok':True}})
if a=='record_status_preflight':v.update(route='record' if {preflight!s} else 'unused',preflight={{'ok':True}} if {preflight!s} else None)
if a=='reduce_status_snapshot':v['snapshot']={{'mill_ready':True,'survey':False,'snapshot':True}}
if a=='status_snapshot_terminal':v['result']={{'ok':True,'mill_ready':True,'survey':False,'snapshot':True}}"""
    )


def test_snapshot_without_preflight_skips_only_preflight_node(tmp_path):
    result = run_graph(
        tmp_path, _body(False), "status-local", path_id="status_snapshot"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_status_preflight"] == "skipped"
        and status["record_status_preflight"] == "succeeded"
        and status["status_snapshot_terminal"] == "succeeded"
    )


def test_explicit_preflight_is_read_then_reduced(tmp_path):
    result = run_graph(
        tmp_path, _body(True), "status-preflight", path_id="status_snapshot"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_status_preflight"] == "succeeded"
        and status["record_status_preflight"] == "succeeded"
        and status["status_snapshot_terminal"] == "succeeded"
    )
