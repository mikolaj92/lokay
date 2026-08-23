"""Native Fala proof for authored self-repair preparation."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_plan_only_skips_all_git_effects(tmp_path):
    body = base_effector(
        """if a=='resolve_self_repair_checkout':v.update(worktree='/tmp/w')
if a=='check_self_repair_mutation_gate':v['route']='planned'
if a.startswith('select_self_repair_'):v['route']='planned'
if a=='select_self_repair_prepare_result':v.update(planned=True,worktree='/tmp/w',base_sha='')
if a=='summarize_self_repair_prepare':v['result']={'planned':True}"""
    )
    result = run_graph(tmp_path, body, "prepare-plan", path_id="self_repair_prepare")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["verify_self_repair_origin"] == "skipped"
        and status["remove_self_repair_worktree"] == "skipped"
        and status["create_self_repair_worktree"] == "skipped"
        and status["summarize_self_repair_prepare"] == "succeeded"
    )
