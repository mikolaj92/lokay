"""Native Fala proofs for authored one-PR publication."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_existing_delivery_pr_skips_issue_probe_and_create(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_create_request':v.update(repo='a/b',issue=7,title='x',body='b',head='ai/7',base='main')
if a=='find_existing_delivery_pr':v.update(route='existing',pull={'number':9})
if a=='record_existing_delivery_pr':v.update(route='existing',pull={'number':9})
if a=='classify_pr_create_issue':v.update(route='terminal',reason='existing_pr')
if a=='pr_create_terminal':v['result']={'ok':True,'existing':True,'pr':9}"""
    )
    result = run_graph(tmp_path, body, "pr-existing", path_id="pr_create_execution")
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["read_pr_create_issue"] == "skipped"
        and status["create_pull_request_effect"] == "skipped"
        and status["pr_create_terminal"] == "succeeded"
    )


def test_open_issue_reaches_one_create_effect(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_create_request':v.update(repo='a/b',issue=7,title='x',body='b',head='ai/7',base='main')
if a=='find_existing_delivery_pr':v.update(route='none',pull=None)
if a=='record_existing_delivery_pr':v.update(route='none',pull=None)
if a=='read_pr_create_issue':v.update(route='classify',issue_state='OPEN')
if a=='classify_pr_create_issue':v.update(route='create',reason='')
if a=='create_pull_request_effect':v.update(route='created',pull={'number':9},planned=False)
if a=='pr_create_terminal':v['result']={'ok':True,'existing':False,'pr':9}"""
    )
    result = run_graph(tmp_path, body, "pr-created", path_id="pr_create_execution")
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["read_pr_create_issue"] == "succeeded"
        and status["create_pull_request_effect"] == "succeeded"
        and status["pr_create_terminal"] == "succeeded"
    )


def test_closed_issue_never_reaches_create_effect(tmp_path):
    body = base_effector(
        """if a=='prepare_pr_create_request':v.update(repo='a/b',issue=7,title='x',body='b',head='ai/7',base='main')
if a=='find_existing_delivery_pr':v.update(route='none',pull=None)
if a=='record_existing_delivery_pr':v.update(route='none',pull=None)
if a=='read_pr_create_issue':v.update(route='classify',issue_state='CLOSED')
if a=='classify_pr_create_issue':v.update(route='terminal',reason='issue_closed',issue_state='CLOSED')
if a=='pr_create_terminal':v['result']={'ok':False,'reason':'issue_closed','issue_state':'CLOSED'}"""
    )
    result = run_graph(tmp_path, body, "pr-closed", path_id="pr_create_execution")
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["create_pull_request_effect"] == "skipped"
        and status["pr_create_terminal"] == "succeeded"
    )
