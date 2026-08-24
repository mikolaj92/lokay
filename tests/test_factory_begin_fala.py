"""Native Fala proofs for explicit factory-begin routing."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_ready_route_persists_workspace_before_terminal(tmp_path):
    body = base_effector("""if a=='inspect_factory_lease':v['route']='preflight'
if a=='run_factory_preflight':v['route']='load'
if a=='reinspect_factory_lease':v['route']='unused'
if a=='select_factory_load_route':v['route']='load'
if a=='load_factory_config':v.update(mode='dry-run',live=False,state_path='/s')
if a=='classify_factory_mode':v['route']='scope'
if a=='select_factory_scope':v['repos']=[]
if a=='read_factory_stuck':v.update(stuck_path='/s',stuck={})
if a=='harvest_factory_children':v['stuck']={}
if a=='persist_factory_stuck':v.update(stuck_path='/s',stuck={})
if a=='create_factory_pass_dir':v['pass_dir']='/pass'
if a=='select_factory_survey_repos':v['survey_repos']=[]
if a=='build_factory_begin_state':v.update(begin={'planned':[]},working={})
if a=='persist_factory_begin_state':v['pass_dir']='/pass'
if a=='classify_factory_begin_terminal':v['kind']='ready'
if a.startswith('build_factory_begin_terminal_'):v['result']={'ok':True,'pass_dir':'/pass'}
if a=='select_factory_begin_terminal':v['result']={'ok':True,'pass_dir':'/pass'}""")
    result = run_graph(tmp_path, body, "factory-begin-ready", path_id="factory_begin")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["restore_factory_lease"] == "skipped"
        and status["run_factory_preflight"] == "succeeded"
        and status["persist_factory_begin_state"] == "succeeded"
        and status["build_factory_begin_terminal_ready"] == "succeeded"
        and status["build_factory_begin_terminal_offline"] == "skipped"
        and status["select_factory_begin_terminal"] == "succeeded"
    )


def test_preflight_failure_skips_workspace_effects(tmp_path):
    body = base_effector(
        """if a=='inspect_factory_lease':v['route']='preflight'
if a=='run_factory_preflight':v['route']='terminal'
if a=='reinspect_factory_lease':v['route']='unused'
if a=='select_factory_load_route':v['route']='terminal'
if a=='classify_factory_mode':v['route']='terminal'
if a=='classify_factory_begin_terminal':v['kind']='preflight_failed'
if a.startswith('build_factory_begin_terminal_'):v['result']={'ok':False,'health':'preflight_failed'}
if a=='select_factory_begin_terminal':v['result']={'ok':False,'health':'preflight_failed'}"""
    )
    result = run_graph(tmp_path, body, "factory-begin-failed", path_id="factory_begin")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["load_factory_config"] == "skipped"
        and status["create_factory_pass_dir"] == "skipped"
        and status["persist_factory_begin_state"] == "skipped"
        and status["build_factory_begin_terminal_preflight_failed"] == "succeeded"
        and status["select_factory_begin_terminal"] == "succeeded"
    )
