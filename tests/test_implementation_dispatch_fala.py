"""Native Fala proofs for serial implementation dispatch."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def test_success_runs_one_launch_and_receipt(tmp_path):
    launch = tmp_path / "launch"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='select_implementation_candidate':v.update(route='candidate',repo='a/b',issue=1)
if a=='inspect_implementation_mutex':v['route']='free'
if a=='select_mutex_outcome':v['route']='free'
if a=='verify_selected_issue_ready':v['route']='ready'
if a=='select_ready_outcome':v['route']='ready'
if a=='launch_issue_to_pr':v['route']='started';Path(%r).write_text('one')
if a=='select_launch_route':v['route']='started'
if a in {'keep_implementation_candidate','drop_stale_implementation_candidate','record_dispatch_failure','label_blocked_dispatch','park_plan_only_dispatch'}:Path(%r).write_text(a)
if a=='record_dispatch_success':v['route']='receipt'
if a=='select_dispatch_outcome':v.update(route='receipt',stuck_changed=True)
if a=='select_blocked_dispatch':v['route']='done'
if a=='summarize_implementation_dispatch':v['result']={'started':1}"""
        % (str(launch), str(wrong))
    )
    r = run_graph(tmp_path, body, "dispatch-success", path_id="implementation_dispatch")
    st = {k: x["status"] for k, x in r["effector_results"].items()}
    assert (
        launch.read_text() == "one"
        and not wrong.exists()
        and st["write_dispatch_receipt"] == "succeeded"
    )


def test_failure_block_and_plan_only_are_direct_edges(tmp_path):
    label = tmp_path / "label"
    park = tmp_path / "park"
    receipt = tmp_path / "receipt"
    body = base_effector(
        """if a=='select_implementation_candidate':v.update(route='candidate',repo='a/b',issue=1)
if a=='inspect_implementation_mutex':v['route']='free'
if a=='select_mutex_outcome':v['route']='free'
if a=='verify_selected_issue_ready':v['route']='ready'
if a=='select_ready_outcome':v['route']='ready'
if a=='launch_issue_to_pr':v['route']='failed'
if a=='select_launch_route':v['route']='failed'
if a=='record_dispatch_failure':v.update(route='blocked',plan_only=True,repo='a/b',issue=1)
if a=='select_dispatch_outcome':v.update(stuck_changed=True,route='blocked',plan_only=True,repo='a/b',issue=1)
if a=='label_blocked_dispatch':Path(%r).write_text('label')
if a=='persist_blocked_dispatch':v.update(route='park',repo='a/b',issue=1)
if a=='select_blocked_dispatch':v.update(route='park',repo='a/b',issue=1)
if a=='park_plan_only_dispatch':Path(%r).write_text('park')
if a=='write_dispatch_receipt':Path(%r).write_text('bad')
if a=='summarize_implementation_dispatch':v['result']={'started':0}"""
        % (str(label), str(park), str(receipt))
    )
    run_graph(tmp_path, body, "dispatch-fail", path_id="implementation_dispatch")
    assert label.exists() and park.exists() and not receipt.exists()


def test_no_candidate_skips_every_effect(tmp_path):
    touched = tmp_path / "touched"
    body = base_effector("""if a=='select_implementation_candidate':v['route']='none'
if a in {'select_mutex_outcome','select_ready_outcome','select_launch_route','select_blocked_dispatch'}:v['route']='none'
if a=='select_dispatch_outcome':v.update(route='done',stuck_changed=False)
if a not in {'select_implementation_candidate','select_mutex_outcome','select_ready_outcome','select_launch_route','select_dispatch_outcome','persist_blocked_dispatch','select_blocked_dispatch','summarize_implementation_dispatch'}:Path(%r).write_text(a)
if a=='summarize_implementation_dispatch':v['result']={'started':0}""" % str(touched))
    run_graph(tmp_path, body, "dispatch-none", path_id="implementation_dispatch")
    assert not touched.exists()


def test_mutex_keep_skips_physical_gate_and_launch(tmp_path):
    keep = tmp_path / "keep"
    launch = tmp_path / "launch"
    body = base_effector(
        """if a=='select_implementation_candidate':v.update(route='candidate',repo='a/b',issue=1)
if a=='inspect_implementation_mutex':v['route']='keep'
if a=='select_mutex_outcome':v['route']='keep'
if a in {'select_ready_outcome','select_launch_route'}:v['route']='none'
if a=='keep_implementation_candidate':Path(%r).write_text('keep')
if a in {'verify_selected_issue_ready','launch_issue_to_pr'}:Path(%r).write_text(a)
if a=='select_dispatch_outcome':v.update(route='done',stuck_changed=False)
if a=='select_blocked_dispatch':v['route']='done'
if a=='summarize_implementation_dispatch':v['result']={'started':0}"""
        % (str(keep), str(launch))
    )
    run_graph(tmp_path, body, "dispatch-mutex", path_id="implementation_dispatch")
    assert keep.exists() and not launch.exists()


def test_stale_gate_drops_without_launch(tmp_path):
    drop = tmp_path / "drop"
    launch = tmp_path / "launch"
    body = base_effector(
        """if a=='select_implementation_candidate':v.update(route='candidate',repo='a/b',issue=1)
if a=='inspect_implementation_mutex':v['route']='free'
if a=='select_mutex_outcome':v['route']='free'
if a=='verify_selected_issue_ready':v['route']='stale'
if a=='select_ready_outcome':v['route']='stale'
if a=='select_launch_route':v['route']='none'
if a=='drop_stale_implementation_candidate':Path(%r).write_text('drop')
if a=='launch_issue_to_pr':Path(%r).write_text('launch')
if a=='select_dispatch_outcome':v.update(route='done',stuck_changed=False)
if a=='select_blocked_dispatch':v['route']='done'
if a=='summarize_implementation_dispatch':v['result']={'started':0}"""
        % (str(drop), str(launch))
    )
    run_graph(tmp_path, body, "dispatch-stale", path_id="implementation_dispatch")
    assert drop.exists() and not launch.exists()
