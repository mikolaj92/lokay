"""Native Fala proof for one inbox-survey catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_inbox_survey_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_inbox_survey':v.update(repos=['o/r'])
if a=='inbox_survey_catalog':v.update(remaining_inbox=4)
if a=='update_inbox_survey_stamp':v['result']={'remaining_inbox':4}"""
    )
    result = run_graph(tmp_path, body, "inbox-catalog", path_id="survey_inbox")
    order = [
        "prepare_inbox_survey",
        "inbox_survey_catalog",
        "update_inbox_survey_stamp",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert list(statuses) == order
    assert not any(
        name.startswith("select_inbox_repo_")
        or name.startswith("list_inbox_repo_")
        or name.startswith("classify_inbox_repo_")
        or name.startswith("record_inbox_repo_")
        or name.startswith("reduce_inbox_survey")
        or name.startswith("persist_inbox_survey")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16
