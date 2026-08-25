"""Native Fala proofs for authored self-repair entry."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(route: str) -> str:
    return base_effector(
        f"""if a=='prepare_self_repair_entry':v.update(state_path='/tmp/state',repo='mikolaj92/lokay',issue=7,fingerprint='abc',incident_url='u',carrier_ok=True,executor_enabled=True)
if a=='classify_self_repair_entry':v.update(route='{route}',reason='' if '{route}'=='run' else 'carrier_unhealthy')
if a.startswith('record_self_repair_entry_'):v.update(route='recorded')
if a=='run_authored_self_repair':v.update(route='classify',path={{'ok':True,'restart_required':True,'commit':'abc'}})
if a=='record_authored_self_repair':v.update(route='classify' if '{route}'=='run' else 'unused',path={{'ok':True,'restart_required':True,'commit':'abc'}} if '{route}'=='run' else {{}})
if a=='classify_self_repair_entry_outcome':v.update(route='restart' if '{route}'=='run' else 'terminal',reason='' if '{route}'=='run' else 'carrier_unhealthy',path={{'ok':True,'restart_required':True,'commit':'abc'}} if '{route}'=='run' else {{}})
if a=='write_self_repair_restart_marker':v.update(route='written',commit='abc')
if a=='select_self_repair_entry_result':v.update(route='success' if '{route}'=='run' else 'failure',result={{'ok':True,'health':'restart_required'}} if '{route}'=='run' else {{'ok':False,'health':'self_repair_failed'}})
if a=='self_repair_entry_terminal':v['result']={{'ok':True,'health':'restart_required'}} if '{route}'=='run' else {{'ok':False,'health':'self_repair_failed'}}"""
    )


def test_ineligible_entry_records_failure_without_running_repair(tmp_path):
    result = run_graph(
        tmp_path, _body("terminal"), "sre-terminal", path_id="self_repair_entry"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_authored_self_repair"] == "skipped"
        and status["write_self_repair_restart_marker"] == "skipped"
        and status["record_self_repair_entry_failure"] == "succeeded"
    )


def test_eligible_entry_runs_one_repair_and_writes_restart(tmp_path):
    result = run_graph(
        tmp_path, _body("run"), "sre-success", path_id="self_repair_entry"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_authored_self_repair"] == "succeeded"
        and status["write_self_repair_restart_marker"] == "succeeded"
        and status["record_self_repair_entry_success"] == "succeeded"
        and status["record_self_repair_entry_failure"] == "skipped"
    )
