"""Native Fala proof for explicit inbox repository slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_one_survey_repo_and_empty_rest(tmp_path):
    body = base_effector("""if a=='prepare_inbox_survey':v.update(repos=['o/r'])
if a.startswith('select_inbox_repo_'):v.update(route='survey' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '')
if a.startswith('list_inbox_repo_'):v.update(route='listed',issues=[])
if a.startswith('classify_inbox_repo_') or a.startswith('record_inbox_repo_'):v.update(route='record' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '')
if a=='reduce_inbox_survey':v['state']={}
if a=='persist_inbox_survey':v.update(remaining_inbox=0)
if a=='update_inbox_survey_stamp':v['result']={'remaining_inbox':0}""")
    result = run_graph(tmp_path, body, "inbox-one", path_id="survey_inbox")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_inbox_repo_1"] == "succeeded"
        and status["list_inbox_repo_2"] == "skipped"
        and status["update_inbox_survey_stamp"] == "succeeded"
    )
