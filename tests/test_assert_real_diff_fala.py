"""Native Fala proofs for authored physical real-diff assertion."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _common(extra: str) -> str:
    return base_effector(
        """if a=='inspect_real_diff_worktree':v.update(route='read',worktree='/tmp/w')
if a=='read_real_diff_paths':v.update(route='classify',paths=['src/a.py'],base='origin/main')
if a=='classify_real_diff_kind':v['kind']='real'
if a=='read_real_diff_localize_scope':v.update(route='scope',paths=['src/a.py'])
if a=='read_real_diff_issue_scope':v.update(route='none',paths=[])
if a=='classify_ticket_scope_presence':v.update(route='continue',required_paths=[])
if a=='classify_ticket_scope_extra':v.update(route='continue',extra_paths=[])
if a=='classify_localized_diff_scope':v.update(route='continue',off_goal_paths=[])
if a=='classify_real_diff_progress':v.update(route='real',reason='')
""" + extra
    )


def test_real_diff_reaches_closed_real_terminal(tmp_path):
    body = _common(
        """if a=='real_diff_terminal':v['result']={'ok':True,'real':True,'kind':'real','paths':['src/a.py']}"""
    )
    result = run_graph(
        tmp_path, body, "real-diff", path_id="assert_real_diff_execution"
    )
    assert all(x["status"] == "succeeded" for x in result["effector_results"].values())


def test_ticket_scope_miss_is_terminal_without_reinterpretation(tmp_path):
    body = _common(
        """if a=='classify_ticket_scope_presence':v.update(route='terminal',reason='ticket_scope_miss',required_paths=['src/b.py'])
if a=='classify_ticket_scope_extra':v.update(route='continue',extra_paths=[])
if a=='classify_localized_diff_scope':v.update(route='terminal',reason='ticket_scope_miss')
if a=='classify_real_diff_progress':v.update(route='terminal',reason='ticket_scope_miss')
if a=='real_diff_terminal':v['result']={'ok':False,'real':False,'reason':'ticket_scope_miss'}"""
    )
    result = run_graph(
        tmp_path, body, "scope-miss", path_id="assert_real_diff_execution"
    )
    assert result["effector_results"]["real_diff_terminal"]["status"] == "succeeded"
