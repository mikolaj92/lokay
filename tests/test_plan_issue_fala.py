"""Native Fala proofs for authored deterministic issue planning."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(route: str) -> str:
    return base_effector(
        f"""if a=='prepare_issue_plan_request':v.update(worktree='/w',issue={{'repo':'a/b','number':7}},rel_path='.lokay/approach.md')
if a=='build_issue_approach':v.update(plan={{}},source='deterministic',content='# Approach',approach_path='/w/.lokay/approach.md')
if a=='authorize_issue_plan_write':v.update(route='{route}',live={route=='write'!s})
if a=='write_issue_approach':v.update(route='written')
if a=='record_issue_approach_write':v.update(route='written' if '{route}'=='write' else 'planned')
if a=='issue_plan_terminal':v['result']={{'ok':True,'wrote':{route=='write'!s},'planned':{route!='write'!s}}}"""
    )


def test_dry_run_skips_write_and_reaches_planned_terminal(tmp_path):
    result = run_graph(
        tmp_path, _body("planned"), "plan-dry", path_id="plan_issue_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["write_issue_approach"] == "skipped"
        and status["record_issue_approach_write"] == "succeeded"
    )


def test_live_authorized_path_writes_once(tmp_path):
    result = run_graph(
        tmp_path, _body("write"), "plan-live", path_id="plan_issue_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["write_issue_approach"] == "succeeded"
        and status["issue_plan_terminal"] == "succeeded"
    )
