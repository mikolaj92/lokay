"""Native Fala proof for explicit self-repair validation branches."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_clean_candidate_without_untracked_paths(tmp_path):
    body = base_effector(
        """if a in {'read_self_repair_candidate_state','classify_self_repair_candidate_diff','validate_self_repair_identity_request','inspect_self_repair_candidate_identity','select_self_repair_identity_gate','verify_self_repair_candidate_identity','run_self_repair_tests'}:v.update(route='tests',worktree='/tmp/w',base_sha='',expected_subject='')
if a=='list_self_repair_untracked_paths':v.update(route='paths',paths=[],worktree='/tmp/w')
if a.startswith('select_self_repair_untracked_') or a.startswith('record_self_repair_untracked_'):v['route']='empty'
if a=='reduce_self_repair_untracked_checks':v.update(route='tracked',worktree='/tmp/w',base_sha='')
if a.startswith('check_self_repair_tracked_'):v.update(route='valid',worktree='/tmp/w',base_sha='')
if a=='select_self_repair_committed_need':v.update(route='no_base',worktree='/tmp/w',base_sha='')
if a=='select_self_repair_committed_gate':v.update(route='valid',worktree='/tmp/w',base_sha='',expected_subject='')
if a=='recheck_self_repair_identity':v.update(validated_commit='',worktree='/tmp/w')
if a=='summarize_self_repair_validation':v['result']={'validated':True}"""
    )
    result = run_graph(tmp_path, body, "validate-clean", path_id="self_repair_validate")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["check_self_repair_untracked_1"] == "skipped"
        and status["check_self_repair_tracked_committed"] == "skipped"
        and status["summarize_self_repair_validation"] == "succeeded"
    )
