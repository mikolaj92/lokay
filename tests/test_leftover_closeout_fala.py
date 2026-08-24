"""Native Fala proof for leftover-closeout repo, label, and candidate slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_one_repo_two_labels_one_deduplicated_candidate(tmp_path):
    body = base_effector(
        """if a=='prepare_leftover_closeout':v.update(route='probe',repos=['o/r'],labels=['work:ready','ai:ready'])
if a.startswith('select_leftover_repo_'):v.update(route='labels' if a.endswith('_1') else 'empty',repo='o/r',labels=['work:ready','ai:ready'])
if a.startswith('select_leftover_label_'):v.update(route='probe' if '_1_' in a else 'empty',repo='o/r',label='work:ready')
if a.startswith('list_leftover_label_'):v.update(route='listed',numbers=[7])
if a.startswith('classify_leftover_label_') or a.startswith('record_leftover_label_'):v.update(route='record',candidates=[{'repo':'o/r','number':7}])
if a.startswith('record_leftover_repo_'):v.update(route='record' if a.endswith('_1') else 'empty',repo='o/r',candidates=[{'repo':'o/r','number':7}] if a.endswith('_1') else [])
if a=='reduce_leftover_candidates':v.update(route='mutate',candidates=[{'repo':'o/r','number':7}])
if a.startswith('select_leftover_candidate_'):v.update(route='park' if a.endswith('_1') else 'empty',repo='o/r',number=7)
if a.startswith('park_leftover_candidate_') or a.startswith('record_leftover_candidate_'):v.update(route='removed')
if a=='reduce_leftover_closeout':v.update(leftover_closed=1)
if a=='update_leftover_stamp':v['result']={'leftover_closed':1}"""
    )
    result = run_graph(tmp_path, body, "leftover-one", path_id="leftover_closeout")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_leftover_label_1_1"] == "succeeded"
        and status["list_leftover_label_2_1"] == "skipped"
        and status["park_leftover_candidate_1"] == "succeeded"
        and status["park_leftover_candidate_2"] == "skipped"
        and status["update_leftover_stamp"] == "succeeded"
    )


def test_recent_empty_skips_all_github_and_mutation_slots(tmp_path):
    body = base_effector(
        """if a=='prepare_leftover_closeout':v.update(route='skip',repos=['o/r'],labels=['work:ready'])
if a.startswith('select_leftover_repo_'):v.update(route='empty')
if a.startswith('select_leftover_label_'):v.update(route='empty')
if a.startswith('classify_leftover_label_') or a.startswith('record_leftover_label_'):v.update(route='empty',candidates=[])
if a.startswith('record_leftover_repo_'):v.update(route='empty',candidates=[])
if a=='reduce_leftover_candidates':v.update(route='skip',candidates=[])
if a.startswith('select_leftover_candidate_') or a.startswith('record_leftover_candidate_'):v.update(route='empty')
if a=='reduce_leftover_closeout':v.update(skipped=True,reason='recent_empty')
if a=='update_leftover_stamp':v['result']={'skipped':True}"""
    )
    result = run_graph(tmp_path, body, "leftover-skip", path_id="leftover_closeout")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_leftover_label_1_1"] == "skipped"
        and status["park_leftover_candidate_1"] == "skipped"
        and status["update_leftover_stamp"] == "succeeded"
    )
