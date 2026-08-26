"""Native Fala proof: parent four-step factory and same-pass next issue."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_parked_row_selects_next_and_dispatches_same_pass(tmp_path):
    body = base_effector(
        """if a=='self_repair':v.update(route='pass',pass_dir='p')
if a=='pr_triage':v.update(route='prs')
if a=='stale_worktree_reap':v.update(route='reaped')
if a=='issue_triage':v.update(route='no',queue_route='parked')
if a=='select_next_issue':v.update(route='yes',advanced=True,repo='a/two',issue=8)
if a=='issue_to_pr':v.update(route='done')
if a=='pr_triage_after':v.update(route='prs')
if a=='record_pass':v.update(result={'ok':True,'health':'progress'})
if a=='factory_pass_terminal':v['result']={'ok':True,'health':'progress'}"""
    )
    result = run_graph(tmp_path, body, "issue-next-row", path_id="factory_pass")
    statuses = {k: x["status"] for k, x in result["effector_results"].items()}
    assert statuses["issue_triage"] == "succeeded"
    assert statuses["select_next_issue"] == "succeeded"
    assert statuses["issue_to_pr"] == "succeeded"
    assert statuses["pr_triage_after"] == "succeeded"


def test_ready_row_skips_next_select(tmp_path):
    body = base_effector(
        """if a=='self_repair':v.update(route='pass',pass_dir='p')
if a=='pr_triage':v.update(route='prs')
if a=='stale_worktree_reap':v.update(route='reaped')
if a=='issue_triage':v.update(route='yes',queue_route='ready')
if a=='select_next_issue':v.update(route='yes')
if a=='issue_to_pr':v.update(route='done')
if a=='pr_triage_after':v.update(route='prs')
if a=='record_pass':v.update(result={'ok':True,'health':'progress'})
if a=='factory_pass_terminal':v['result']={'ok':True,'health':'progress'}"""
    )
    result = run_graph(tmp_path, body, "issue-ready", path_id="factory_pass")
    statuses = {k: x["status"] for k, x in result["effector_results"].items()}
    assert statuses["select_next_issue"] == "skipped"
    assert statuses["issue_to_pr"] == "succeeded"
    assert statuses["pr_triage_after"] == "succeeded"


def test_factory_leftover_fail_hosts_issue_work_not_recovery(tmp_path):
    body = base_effector(
        """if a=='self_repair':v.update(route='pass',pass_dir='p')
if a=='pr_triage':v.update(route='prs')
if a=='stale_worktree_reap':v.update(route='skip',leftover={'skipped':True,'reason':'candidates_exceed_slots'})
if a=='issue_triage':v.update(route='yes')
if a=='select_next_issue':v.update(route='no')
if a=='issue_to_pr':v.update(route='done')
if a=='pr_triage_after':v.update(route='prs')
if a=='record_pass':v.update(result={'ok':True,'health':'progress'})
if a=='factory_pass_terminal':v['result']={'ok':True,'health':'progress'}"""
    )
    result = run_graph(tmp_path, body, "factory-leftover-skip", path_id="factory_pass")
    statuses = {k: x["status"] for k, x in result["effector_results"].items()}
    assert statuses["pr_triage"] == "succeeded"
    assert statuses["stale_worktree_reap"] == "succeeded"
    assert statuses["issue_triage"] == "succeeded"
    assert statuses["record_pass"] == "succeeded"
    assert "recovery_mill" not in statuses
