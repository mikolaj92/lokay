"""Native Fala proofs for explicit PR repair routing."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def defaults():
    return """if a=='select_evidence_repair':v['route']='not_applicable'
if a=='select_repair_test_recheck':v['route']='not_applicable'"""


def test_repaired_skips_retry_evidence_and_pushes(tmp_path):
    push = tmp_path / "push"
    wrong = tmp_path / "wrong"
    body = base_effector(
        defaults()
        + """
if a=='validate_initial_repair':v.update(route='valid',decision={'verdict':'repaired'})
if a=='select_initial_repair':v.update(route='repaired',evidence_kind='none',decision={'verdict':'repaired'})
if a=='finalize_repair_result':v.update(route='repaired',decision={'verdict':'repaired'})
if a=='test_local':v.update(tested=True)
if a=='select_repair_test':v['route']='pass'
if a=='select_test_repair_result':v['route']='not_applicable'
if a=='finalize_repair_tests':v['route']='publish'
if a=='push':Path(%r).write_text('ran')
if a in {'pr_repair_retry_agent','evidence_repair_agent','pr_test_repair_agent'}:Path(%r).write_text(a)"""
        % (str(push), str(wrong))
    )
    result = run_graph(tmp_path, body, "repair-ok", path_id="pr_repair")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["push"] == "succeeded"
        and st["pr_repair_retry_agent"] == "skipped"
        and st["evidence_repair_agent"] == "skipped"
        and st["pr_test_repair_agent"] == "skipped"
    )
    assert push.exists() and not wrong.exists()


def test_invalid_json_gets_one_retry_then_human(tmp_path):
    retry = tmp_path / "retry"
    body = base_effector(
        defaults()
        + """
if a=='validate_initial_repair':v.update(route='retry',validation_error='bad')
if a=='pr_repair_retry_agent':Path(%r).write_text('ran')
if a=='validate_repair_retry':v['route']='retry'
if a=='select_initial_repair':v.update(route='human',evidence_kind='none',decision={'verdict':'needs_human'})
if a=='finalize_repair_result':v.update(route='human',decision={'verdict':'needs_human'})
if a in {'select_repair_test','select_test_repair_result','finalize_repair_tests'}:v['route']='not_applicable'"""
        % str(retry)
    )
    result = run_graph(tmp_path, body, "repair-retry", path_id="pr_repair")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["pr_repair_retry_agent"] == "succeeded"
        and st["pr_repair_manual"] == "succeeded"
        and st["push"] == "skipped"
        and retry.exists()
    )


def test_only_selected_repair_evidence_runs(tmp_path):
    chosen = tmp_path / "chosen"
    wrong = tmp_path / "wrong"
    body = base_effector(
        defaults()
        + """
if a=='validate_initial_repair':v.update(route='valid',decision={'verdict':'needs_evidence','evidence_kind':'review_findings'})
if a=='select_initial_repair':v.update(route='evidence',evidence_kind='review_findings',decision={'verdict':'needs_evidence'})
if a=='collect_repair_review_findings':Path(%r).write_text('ran')
if a in {'collect_repair_pr_metadata','collect_repair_changed_files','collect_repair_test_contract'}:Path(%r).write_text(a)
if a=='validate_evidence_repair':v.update(route='valid',decision={'verdict':'needs_human'})
if a=='select_evidence_repair':v.update(route='human',decision={'verdict':'needs_human'})
if a=='finalize_repair_result':v.update(route='human',decision={'verdict':'needs_human'})
if a in {'select_repair_test','select_test_repair_result','finalize_repair_tests'}:v['route']='not_applicable'"""
        % (str(chosen), str(wrong))
    )
    result = run_graph(tmp_path, body, "repair-evidence", path_id="pr_repair")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["collect_repair_review_findings"] == "succeeded" and all(
        st[x] == "skipped"
        for x in (
            "collect_repair_pr_metadata",
            "collect_repair_changed_files",
            "collect_repair_test_contract",
        )
    )
    assert chosen.exists() and not wrong.exists()


def test_red_test_runs_one_test_repair_then_terminal(tmp_path):
    agent = tmp_path / "agent"
    body = base_effector(defaults() + """
if a=='validate_initial_repair':v.update(route='valid',decision={'verdict':'repaired'})
if a=='select_initial_repair':v.update(route='repaired',evidence_kind='none',decision={'verdict':'repaired'})
if a=='finalize_repair_result':v.update(route='repaired',decision={'verdict':'repaired'})
if a=='test_local':v.update(tested=True,recorded_red=True)
if a=='select_repair_test':v['route']='fail'
if a=='pr_test_repair_agent':Path(%r).write_text('ran')
if a=='validate_test_repair':v['route']='retry'
if a=='select_test_repair_result':v['route']='terminal'
if a=='finalize_repair_tests':v['route']='terminal'""" % str(agent))
    result = run_graph(tmp_path, body, "repair-red", path_id="pr_repair")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["pr_test_repair_agent"] == "succeeded"
        and st["pr_repair_terminal"] == "succeeded"
        and st["push"] == "skipped"
        and agent.exists()
    )
