"""Native Fala proof for explicit stale-stage recovery slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_recent_empty_skips_all_catalog_probes(tmp_path):
    body = base_effector(
        """if a=='prepare_stale_implementing_reap':v.update(route='recent_empty',repos=[])
if a.startswith('select_stale_repo_'):v['route']='empty'
if a.startswith('reduce_stale_repo_'):v['route']='empty'
if a=='reduce_stale_implementing_probe':v.update(route='empty',candidates=[])
if a=='check_stale_mutation_gate':v.update(route='no_candidates',apply=False)
if a.startswith('select_stale_candidate_') or a.startswith('record_stale_candidate_'):v['route']='empty'
if a=='reduce_stale_reap_effects':v.update(reaped=[],reaped_count=0)
if a=='summarize_stale_implementing_reap':v['result']={'skipped':True,'reason':'recent_empty'}"""
    )
    result = run_graph(
        tmp_path, body, "stale-recent", path_id="reap_stale_implementing"
    )
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["list_stale_repo_label_1_1"] == "skipped"
        and status["restore_stale_issue_ready_1"] == "skipped"
        and status["summarize_stale_implementing_reap"] == "succeeded"
    )
