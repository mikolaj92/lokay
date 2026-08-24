"""Native Fala proofs for exact self-repair activation."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_planned_activation_has_no_git_effects(tmp_path):
    body = base_effector(
        """if a=='prepare_self_repair_activation':v.update(route='planned',planned=True,commit='abc',path='/tmp/lokay')
if a=='classify_canonical_checkout':v.update(route='terminal',reason='planned')
if a=='record_canonical_fetch' or a=='record_recovery_fast_forward' or a=='record_recovery_head_ancestry':v.update(route='unused')
if a=='classify_activated_head':v.update(route='terminal',reason='planned')
if a=='self_repair_activation_terminal':v['result']={'ok':True,'planned':True,'activated':False,'commit':'abc'}"""
    )
    result = run_graph(
        tmp_path, body, "activate-planned", path_id="self_repair_activate_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["read_canonical_checkout_status"] == "skipped"
        and status["fetch_canonical_main"] == "skipped"
        and status["fast_forward_recovery_commit"] == "skipped"
        and status["self_repair_activation_terminal"] == "succeeded"
    )


def test_clean_activation_runs_exact_effect_chain(tmp_path):
    body = base_effector(
        """if a=='prepare_self_repair_activation':v.update(route='status',planned=False,commit='abc',path='/tmp/lokay')
if a=='read_canonical_checkout_status':v.update(route='classify',dirty=False)
if a=='classify_canonical_checkout':v.update(route='clean')
if a=='fetch_canonical_main':v.update(route='fetched')
if a=='record_canonical_fetch':v.update(route='fetched')
if a=='fast_forward_recovery_commit':v.update(route='merged')
if a=='record_recovery_fast_forward':v.update(route='merged')
if a=='record_recovery_head_ancestry':v.update(route='unused')
if a=='read_activated_head':v.update(route='classify',head='abc')
if a=='classify_activated_head':v.update(route='exact',head='abc')
if a=='self_repair_activation_terminal':v['result']={'ok':True,'planned':False,'activated':True,'commit':'abc'}"""
    )
    result = run_graph(
        tmp_path, body, "activate-exact", path_id="self_repair_activate_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["fetch_canonical_main"] == "succeeded"
        and status["fast_forward_recovery_commit"] == "succeeded"
        and status["read_activated_head"] == "succeeded"
        and status["check_recovery_ancestor_head"] == "skipped"
    )


def test_dirty_published_commit_never_fetches_or_merges(tmp_path):
    body = base_effector(
        """if a=='prepare_self_repair_activation':v.update(route='status',commit='abc',path='/tmp/lokay')
if a=='read_canonical_checkout_status':v.update(route='classify',dirty=True)
if a=='classify_canonical_checkout':v.update(route='dirty')
if a=='check_dirty_commit_on_origin':v.update(route='published',reason='dirty_tree',published=True)
if a=='record_canonical_fetch' or a=='record_recovery_fast_forward' or a=='record_recovery_head_ancestry':v.update(route='unused')
if a=='classify_activated_head':v.update(route='terminal',reason='dirty_tree',published=True)
if a=='self_repair_activation_terminal':v['result']={'ok':True,'activated':False,'published':True,'reason':'dirty_tree','commit':'abc'}"""
    )
    result = run_graph(
        tmp_path, body, "activate-dirty", path_id="self_repair_activate_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["check_dirty_commit_on_origin"] == "succeeded"
        and status["fetch_canonical_main"] == "skipped"
        and status["fast_forward_recovery_commit"] == "skipped"
    )
