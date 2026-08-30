"""Native Fala proof for declared local-test execution."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_green_full_suite_skips_scope_and_writes_cache(tmp_path):
    body = base_effector(
        """if a=='inspect_test_declaration':v.update(route='test',worktree='/w',test_argv=['true'])
if a=='read_test_green_cache':v.update(route='miss',key='k')
if a=='run_declared_tests':v.update(route='green',tests='true')
if a=='select_declared_test_outcome':v.update(route='cache')
if a=='derive_changed_test_scope':v.update(route='none',argv=[])
if a=='select_green_test_result':v.update(route='green',source={'tests':'true'})
if a=='write_test_green_cache':v.update(written=True,tests='true')
if a=='classify_test_terminal':v['kind']='green'
if a.startswith('build_test_terminal_'):v['result']={'ok':True,'tested':True}
if a=='select_test_terminal':v['result']={'ok':True,'tested':True}"""
    )
    result = run_graph(tmp_path, body, "test-green", path_id="test_local_execution")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_declared_tests"] == "succeeded"
        and status["run_changed_scope_tests"] == "skipped"
        and status["write_test_green_cache"] == "succeeded"
        and status["select_test_terminal"] == "succeeded"
    )

def test_no_declared_test_reaches_inspection_terminal(tmp_path):
    body = base_effector(
        "if a=='inspect_test_declaration':v.update(route='terminal',result={'ok':True,'skipped':True,'reason':'no_declared_test'})\n"
        "if a=='read_test_green_cache':v.update(route='terminal',key='',cached={})\n"
        "if a=='select_declared_test_outcome':v.update(route='terminal')\n"
        "if a=='derive_changed_test_scope':v.update(route='none',argv=[])\n"
        "if a=='select_green_test_result':v.update(route='none',source={})\n"
        "if a=='write_test_green_cache':v.update(written=False,tests='')\n"
        "if a=='classify_test_terminal':v['kind']='inspection'\n"
        "if a=='build_test_terminal_inspection':v['result']={'ok':True,'skipped':True,'reason':'no_declared_test'}\n"
        "if a.startswith('build_test_terminal_'):v.setdefault('result',{'ok':True,'skipped':True,'reason':'no_declared_test'})\n"
        "if a=='select_test_terminal':v['result']={'ok':True,'skipped':True,'reason':'no_declared_test'}"
    )
    result = run_graph(tmp_path, body, "test-skip", path_id="test_local_execution")
    assert result.get("ok") is True, result
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert status["read_test_green_cache"] == "succeeded"
    assert status["run_declared_tests"] == "skipped"
    assert status["select_test_terminal"] == "succeeded"

