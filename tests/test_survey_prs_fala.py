"""Native Fala proof for explicit PR-survey repository slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_one_pr_repo_and_empty_rest(tmp_path):
    body = base_effector("""if a=='prepare_pr_survey':v.update(repos=['o/r'])
if a.startswith('select_pr_survey_repo_'):v.update(route='survey' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '')
if a.startswith('list_pr_survey_repo_'):v.update(route='listed',prs=[])
if a.startswith('classify_pr_survey_repo_') or a.startswith('record_pr_survey_repo_'):v.update(route='record' if a.endswith('_1') else 'empty',repo='o/r' if a.endswith('_1') else '')
if a=='reduce_pr_survey':v['state']={}
if a=='persist_pr_survey':v.update(remaining_prs=0)
if a=='update_pr_survey_stamp':v['result']={'remaining_prs':0}""")
    result = run_graph(tmp_path, body, "pr-survey-one", path_id="survey_prs")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_pr_survey_repo_1"] == "succeeded"
        and status["list_pr_survey_repo_2"] == "skipped"
        and status["update_pr_survey_stamp"] == "succeeded"
    )
