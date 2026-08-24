"""Native Fala proofs for authored one-issue stage transition."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(state: str) -> str:
    return base_effector(
        f"""if a=='prepare_stage_transition':v.update(repo='a/b',issue=7,stage='ready',remove_labels=['old'],add_labels=['ai:ready'],comment='receipt',live=True)
if a=='read_stage_issue':v.update(route='classify',issue_state='{state}')
if a=='classify_stage_issue':v.update(route='remove' if '{state}'=='OPEN' else 'terminal',reason='' if '{state}'=='OPEN' else 'issue_closed',issue_state='{state}')
if a=='remove_stage_labels_effect':v.update(route='removed')
if a=='record_stage_removal':v.update(route='removed' if '{state}'=='OPEN' else 'terminal',reason='' if '{state}'=='OPEN' else 'issue_closed')
if a=='add_stage_labels_effect':v.update(route='comment' if '{state}'=='OPEN' else 'terminal')
if a=='comment_stage_receipt_effect':v.update(route='done')
if a=='stage_label_terminal':v['result']={{'ok':True,'applied':True}} if '{state}'=='OPEN' else {{'ok':True,'skipped':True,'reason':'issue_closed'}}"""
    )


def test_open_issue_runs_remove_add_comment_in_order(tmp_path):
    result = run_graph(
        tmp_path, _body("OPEN"), "stage-open", path_id="stage_label_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["remove_stage_labels_effect"] == "succeeded"
        and status["comment_stage_receipt_effect"] == "succeeded"
    )


def test_closed_issue_skips_every_mutation(tmp_path):
    result = run_graph(
        tmp_path, _body("CLOSED"), "stage-closed", path_id="stage_label_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["remove_stage_labels_effect"] == "skipped"
        and status["add_stage_labels_effect"] == "succeeded"
        and status["comment_stage_receipt_effect"] == "skipped"
    )
