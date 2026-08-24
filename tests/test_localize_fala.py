"""Native Fala proofs for authored localization execution."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_explicit_paths_skip_agent_and_reach_write(tmp_path):
    body = base_effector(
        """if a=='prepare_localization_request':v.update(worktree='/w',has_file_hints=True)
if a=='inspect_existing_localization':v.update(existing=[],tree=['src/a.py'],worktree_exists=True)
if a=='classify_localization_route':v['route']='explicit'
if a=='build_explicit_localization':v.update(route='candidate',paths=['src/a.py'],source='bypass')
if a=='build_deterministic_localization':v.update(route='candidate',paths=[])
if a=='build_localization_agent_request':v.update(route='unused',prompt='')
if a=='validate_localization_agent_json' or a=='validate_localization_retry_json':v['route']='unused'
if a=='build_localization_retry':v['route']='unused'
if a=='select_localization_candidate':v.update(route='candidate',paths=['src/a.py'],source='bypass')
if a=='validate_localization_paths':v.update(route='write',paths=['src/a.py'])
if a=='write_localization_evidence':v.update(route='success',paths=['src/a.py'])
if a=='localization_terminal':v['result']={'ok':True,'paths':['src/a.py']}"""
    )
    result = run_graph(
        tmp_path, body, "localize-explicit", path_id="localize_execution"
    )
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_localization_agent"] == "skipped"
        and status["retry_localization_agent"] == "skipped"
        and status["write_localization_evidence"] == "succeeded"
        and status["localization_terminal"] == "succeeded"
    )


def test_invalid_json_gets_one_retry_then_terminal(tmp_path):
    body = base_effector("""if a=='prepare_localization_request':v.update(worktree='/w')
if a=='inspect_existing_localization':v.update(existing=[],tree=['src/a.py'],worktree_exists=True)
if a=='classify_localization_route':v['route']='agent'
if a=='build_explicit_localization' or a=='build_deterministic_localization':v.update(route='candidate',paths=[])
if a=='build_localization_agent_request':v.update(route='agent',prompt='p')
if a=='run_localization_agent' or a=='retry_localization_agent':v.update(route='validate',text='bad')
if a=='validate_localization_agent_json' or a=='validate_localization_retry_json':v.update(route='invalid',validator_error='paths must be a non-empty list')
if a=='build_localization_retry':v.update(route='retry',feedback='exact')
if a=='select_localization_candidate':v.update(route='terminal',reason='invalid_json',paths=[])
if a=='validate_localization_paths':v.update(route='terminal',reason='empty_paths',paths=[])
if a=='write_localization_evidence':v.update(route='terminal',reason='invalid_json')
if a=='localization_terminal':v['result']={'ok':False,'reason':'invalid_json'}""")
    result = run_graph(tmp_path, body, "localize-invalid", path_id="localize_execution")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_localization_agent"] == "succeeded"
        and status["retry_localization_agent"] == "succeeded"
        and status["validate_localization_retry_json"] == "succeeded"
        and status["localization_terminal"] == "succeeded"
    )
