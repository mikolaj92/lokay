"""Native Fala proof for explicit pass-plan repository slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_first_repo_fragment_and_empty_slots(tmp_path):
    body = base_effector("""if a=='prepare_pass_plan':v.update(repos=['a/one'])
if a.startswith('select_plan_repo_'):v.update(route='repo' if a.endswith('_1') else 'empty',repo='a/one' if a.endswith('_1') else '')
if a.startswith('build_repo_plan_fragment_'):v.update(route='fragment',repo='a/one')
if a.startswith('record_repo_plan_fragment_'):v.update(route='fragment' if a.endswith('_1') else 'empty')
if a=='reduce_pass_plan':v['plan']={'triage_targets':[]}
if a=='persist_pass_plan':v.update(triage_count=0)
if a=='summarize_pass_plan':v['result']={'triage_count':0}""")
    result = run_graph(tmp_path, body, "plan-one", path_id="plan_pass")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["build_repo_plan_fragment_1"] == "succeeded"
        and status["build_repo_plan_fragment_2"] == "skipped"
        and status["summarize_pass_plan"] == "succeeded"
    )
