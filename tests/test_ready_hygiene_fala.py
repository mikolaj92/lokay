"""Native Fala proof for ready-hygiene repo and candidate slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_one_repo_one_candidate(tmp_path):
    body = base_effector(
        """if a=='prepare_ready_hygiene':v.update(route='probe',repos=['o/r'])
if a.startswith('select_ready_hygiene_repo_'):v.update(route='probe' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '')
if a.startswith('list_ready_hygiene_repo_'):v.update(route='listed',issues=[])
if a.startswith('classify_ready_hygiene_repo_') or a.startswith('record_ready_hygiene_repo_'):v.update(route='record' if a.endswith('_1') else 'empty')
if a=='reduce_ready_hygiene_candidates':v.update(route='mutate',candidates=[{'repo':'o/r','number':1}])
if a.startswith('select_ready_hygiene_candidate_'):v.update(route='remove' if a.endswith('_1') else 'empty',repo='o/r',number=1)
if a.startswith('remove_ready_hygiene_candidate_'):v.update(route='removed')
if a.startswith('record_ready_hygiene_candidate_'):v.update(route='removed' if a.endswith('_1') else 'empty')
if a=='reduce_ready_hygiene':v.update(cleaned_count=1)
if a=='update_ready_hygiene_stamp':v['result']={'cleaned_count':1}"""
    )
    result = run_graph(tmp_path, body, "ready-hygiene-one", path_id="ready_hygiene")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_ready_hygiene_repo_1"] == "succeeded"
        and status["list_ready_hygiene_repo_2"] == "skipped"
        and status["remove_ready_hygiene_candidate_1"] == "succeeded"
        and status["remove_ready_hygiene_candidate_2"] == "skipped"
        and status["update_ready_hygiene_stamp"] == "succeeded"
    )
