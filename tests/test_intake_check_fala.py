"""Native Fala proofs for authored one mechanical intake check."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(route: str) -> str:
    return base_effector(
        f"""if a=='prepare_intake_check':v.update(route='read',repo='mikolaj92/lokay',issue=7,check='{route}',live=False)
if a=='read_intake_check_issue':v.update(route='resolve',issue={{'repo':'mikolaj92/lokay','number':7,'title':'x','body':'','labels':[],'assignees':[],'url':'u','state':'OPEN'}})
if a=='resolve_intake_check_clone':v['clone_path']=None
if a=='classify_intake_check_route':v['route']='{route}'
if a.startswith('run_intake_') and a.endswith('_check'):v.update(route='selected',check={{'check':'{route}','verdict':'pass','reason':'ok','detail':{{}}}})
if a=='parse_intake_covering_prs':v.update(route='parsed',prs=[])
if a=='select_intake_check_result':v.update(route='selected',check={{'check':'{route}','verdict':'pass','reason':'ok','detail':{{}}}})
if a=='intake_check_terminal':v['result']={{'ok':True,'check':{{'check':'{route}','verdict':'pass'}}}}"""
    )


def test_open_runs_only_open_branch(tmp_path):
    result = run_graph(
        tmp_path, _body("open"), "intake-open", path_id="intake_check_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_intake_open_check"] == "succeeded"
        and status["run_intake_superseded_check"] == "skipped"
        and status["probe_intake_check_shape"] == "skipped"
    )


def test_shape_runs_bounded_probe_and_shape_rule(tmp_path):
    result = run_graph(
        tmp_path, _body("shape"), "intake-shape", path_id="intake_check_execution"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["probe_intake_check_shape"] == "succeeded"
        and status["run_intake_shape_check"] == "succeeded"
        and status["run_intake_open_check"] == "skipped"
    )


def test_duplicate_runs_parser_and_duplicate_rule(tmp_path):
    result = run_graph(
        tmp_path,
        _body("duplicate_ai_pr"),
        "intake-duplicate",
        path_id="intake_check_execution",
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["parse_intake_covering_prs"] == "succeeded"
        and status["run_intake_duplicate_pr_check"] == "succeeded"
        and status["run_intake_ambiguity_check"] == "skipped"
    )
