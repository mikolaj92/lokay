"""Native Fala proof for one ready-survey catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_ready_survey_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_ready_survey':v.update(route='survey',repos=['a/one'],active_repos=['a/one'])
if a=='ready_survey_catalog':v.update(remaining_ready=1,survey_errors=0)
if a=='update_ready_survey_stamp':v['result']={'remaining_ready':1}"""
    )
    result = run_graph(tmp_path, body, "ready-catalog", path_id="survey_ready")
    order = [
        "prepare_ready_survey",
        "ready_survey_catalog",
        "update_ready_survey_stamp",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert set(statuses) == set(order)
    assert not any(
        name.startswith("select_ready_repo_")
        or name.startswith("list_work_ready_")
        or name.startswith("classify_ready_repo_")
        or name.startswith("park_blocked_ready_")
        or name.startswith("record_ready_repo_")
        or name.startswith("reduce_ready_survey")
        or name.startswith("finalize_ready_survey")
        for name in statuses
    )
    assert result.get("ticks_used", 16) <= 16


def test_ready_survey_empty_catalog_finishes_without_64_ticks(tmp_path):
    body = base_effector(
        """if a=='prepare_ready_survey':v.update(route='skip',repos=[],active_repos=[])
if a=='ready_survey_catalog':v.update(skipped=True,remaining_ready=0,survey_errors=0)
if a=='update_ready_survey_stamp':v['result']={'skipped':True}"""
    )
    result = run_graph(tmp_path, body, "ready-empty", path_id="survey_ready")
    statuses = result["effector_results"]
    assert len(statuses) == 3
    assert statuses["ready_survey_catalog"]["status"] == "succeeded"
    assert statuses["update_ready_survey_stamp"]["status"] == "succeeded"
    assert result.get("ticks_used", 16) < 64
