"""Native Fala proofs for authored off-goal relocalization."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_no_localize_skips_diff_restore_and_agent(tmp_path):
    body = base_effector(
        """if a=='inspect_relocalization_evidence':v.update(route='terminal',reason='no_localize')
if a=='read_relocalization_changed_paths':v.update(route='unused',changed=[])
if a=='read_relocalization_issue_paths':v['paths']=[]
if a=='classify_relocalization_residue':v.update(route='continue',restore_paths=[])
if a=='authorize_relocalization_restore':v.update(route='unused',restore_paths=[])
if a=='record_relocalization_restore':v.update(route='none',restored_paths=[])
if a=='classify_relocalization_off_goal':v.update(route='terminal',off_goal_paths=[],reason='on_goal')
if a=='build_relocalization_agent_request':v['route']='unused'
if a=='validate_relocalization_agent_json' or a=='validate_relocalization_retry_json':v['route']='unused'
if a=='build_relocalization_retry':v['route']='unused'
if a=='select_relocalization_validation':v.update(route='terminal',reason='unused')
if a=='validate_relocalization_approval':v.update(route='terminal',approved=[])
if a=='relocalization_terminal':v['result']={'ok':True,'skipped':True,'reason':'no_localize'}"""
    )
    result = run_graph(tmp_path, body, "reloc-none", path_id="relocalize_off_goal")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["restore_relocalization_residue"] == "skipped"
        and status["run_relocalization_agent"] == "skipped"
        and status["write_relocalization_evidence"] == "skipped"
        and status["relocalization_terminal"] == "succeeded"
    )


def test_invalid_agent_json_gets_one_retry(tmp_path):
    body = base_effector(
        """if a=='inspect_relocalization_evidence':v.update(route='read',localized=['src/a.py'])
if a=='read_relocalization_changed_paths':v.update(route='classify',changed=['src/a.py','src/b.py'],base='origin/main')
if a=='read_relocalization_issue_paths':v['paths']=[]
if a=='classify_relocalization_residue':v.update(route='continue',restore_paths=[])
if a=='authorize_relocalization_restore':v.update(route='unused',restore_paths=[])
if a=='record_relocalization_restore':v.update(route='none',restored_paths=[])
if a=='classify_relocalization_off_goal':v.update(route='agent',off_goal_paths=['src/b.py'])
if a=='build_relocalization_agent_request':v.update(route='agent',prompt='p')
if a=='run_relocalization_agent' or a=='retry_relocalization_agent':v.update(route='validate',text='bad')
if a=='validate_relocalization_agent_json' or a=='validate_relocalization_retry_json':v.update(route='invalid',validator_error='bad json')
if a=='build_relocalization_retry':v.update(route='retry',feedback='exact')
if a=='select_relocalization_validation':v.update(route='terminal',reason='invalid_json')
if a=='validate_relocalization_approval':v.update(route='terminal',approved=[])
if a=='relocalization_terminal':v['result']={'ok':True,'skipped':True,'reason':'invalid_json'}"""
    )
    result = run_graph(tmp_path, body, "reloc-invalid", path_id="relocalize_off_goal")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_relocalization_agent"] == "succeeded"
        and status["retry_relocalization_agent"] == "succeeded"
        and status["validate_relocalization_retry_json"] == "succeeded"
        and status["write_relocalization_evidence"] == "skipped"
    )
