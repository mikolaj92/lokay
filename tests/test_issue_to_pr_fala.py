"""Native Fala proofs for the explicit issue implementation branches."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def test_valid_implementation_skips_retry_and_evidence_then_publishes(tmp_path):
    pushed = tmp_path / "push"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='run_agent':v['stdout']='ok'
if a=='validate_coding_result':v.update(route='valid',decision={'verdict':'implemented'})
if a=='select_coding_result':v.update(route='implemented',evidence_kind='none',decision={'verdict':'implemented'})
if a=='select_evidence_coding':v['route']='not_applicable'
if a=='finalize_coding_result':v.update(route='implemented',decision={'verdict':'implemented'})
if a=='test_local':v.update(tested=True)
if a=='select_local_test':v['route']='pass'
if a=='select_repair_result':v['route']='not_applicable'
if a=='select_local_test_recheck':v['route']='not_applicable'
if a=='finalize_local_tests':v['route']='publish'
if a=='push':Path(%r).write_text('ran')
if a in {'coding_retry_agent','evidence_coding_agent','repair_agent'}:Path(%r).write_text(a)"""
        % (str(pushed), str(wrong))
    )
    result = run_graph(tmp_path, body, "implemented", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["coding_retry_agent"] == "skipped"
        and st["evidence_coding_agent"] == "skipped"
        and st["repair_agent"] == "skipped"
    )
    assert st["push"] == "succeeded" and pushed.exists() and not wrong.exists()


def test_invalid_json_runs_one_retry(tmp_path):
    retry = tmp_path / "retry"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='validate_coding_result':v.update(route='retry',validation_error='bad')
if a=='coding_retry_agent':Path(%r).write_text('ran')
if a=='validate_coding_retry':v.update(route='valid',decision={'verdict':'needs_human'})
if a=='select_coding_result':v.update(route='human',evidence_kind='none',decision={'verdict':'needs_human'})
if a=='select_evidence_coding':v['route']='not_applicable'
if a=='finalize_coding_result':v.update(route='human',decision={'verdict':'needs_human'})
if a in {'select_local_test','select_repair_result','select_local_test_recheck','finalize_local_tests'}:v['route']='not_applicable'"""
        % str(retry)
    )
    result = run_graph(tmp_path, body, "retry", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["coding_retry_agent"] == "succeeded"
        and st["coding_manual"] == "succeeded"
        and st["push"] == "skipped"
        and retry.exists()
    )


def test_evidence_runs_only_selected_collector(tmp_path):
    chosen = tmp_path / "chosen"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='validate_coding_result':v.update(route='valid',decision={'verdict':'needs_evidence','evidence_kind':'test_contract'})
if a=='select_coding_result':v.update(route='evidence',evidence_kind='test_contract',decision={'verdict':'needs_evidence'})
if a=='collect_coding_test_contract':Path(%r).write_text('ran')
if a in {'collect_coding_issue_snapshot','collect_coding_repo_structure','collect_coding_localized_diff'}:Path(%r).write_text(a)
if a=='validate_evidence_coding':v.update(route='valid',decision={'verdict':'needs_human'})
if a=='select_evidence_coding':v.update(route='human',decision={'verdict':'needs_human'})
if a=='finalize_coding_result':v.update(route='human',decision={'verdict':'needs_human'})
if a in {'select_local_test','select_repair_result','select_local_test_recheck','finalize_local_tests'}:v['route']='not_applicable'"""
        % (str(chosen), str(wrong))
    )
    result = run_graph(tmp_path, body, "evidence", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["collect_coding_test_contract"] == "succeeded" and all(
        st[x] == "skipped"
        for x in (
            "collect_coding_issue_snapshot",
            "collect_coding_repo_structure",
            "collect_coding_localized_diff",
        )
    )
    assert chosen.exists() and not wrong.exists()


def test_red_test_runs_one_repair_then_terminal(tmp_path):
    repair = tmp_path / "repair"
    body = base_effector("""if a=='resolve_implementation_issue':v['route']='open'
if a=='validate_coding_result':v.update(route='valid',decision={'verdict':'implemented'})
if a=='select_coding_result':v.update(route='implemented',evidence_kind='none',decision={'verdict':'implemented'})
if a=='select_evidence_coding':v['route']='not_applicable'
if a=='finalize_coding_result':v.update(route='implemented',decision={'verdict':'implemented'})
if a=='test_local':v.update(tested=True,recorded_red=True)
if a=='select_local_test':v['route']='fail'
if a=='repair_agent':Path(%r).write_text('ran')
if a=='validate_repair_result':v['route']='retry'
if a=='select_repair_result':v['route']='terminal'
if a=='select_local_test_recheck':v['route']='not_applicable'
if a=='finalize_local_tests':v['route']='repair_terminal'""" % str(repair))
    result = run_graph(tmp_path, body, "repair", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["repair_agent"] == "succeeded"
        and st["coding_repair_terminal"] == "succeeded"
        and st["push"] == "skipped"
        and repair.exists()
    )


def test_parent_gate_invokes_delivery_only_when_no_delivery_exists(tmp_path):
    delivery = tmp_path / "delivery"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='resolve_existing_delivery':v['route']='deliver'
if a=='issue_to_pr_subflow':Path(%r).write_text('ran')
if a in {'close_existing_delivery','issue_to_pr_no_effect'}:Path(%r).write_text(a)"""
        % (str(delivery), str(wrong))
    )
    result = run_graph(tmp_path, body, "parent-deliver", path_id="issue_to_pr")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["issue_to_pr_subflow"] == "succeeded"
        and st["close_existing_delivery"] == "skipped"
        and st["issue_to_pr_no_effect"] == "skipped"
    )
    assert delivery.exists() and not wrong.exists()


def test_parent_gate_closeout_skips_delivery_subflow(tmp_path):
    closeout = tmp_path / "closeout"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='resolve_existing_delivery':v['route']='closeout'
if a=='close_existing_delivery':Path(%r).write_text('ran')
if a in {'issue_to_pr_subflow','issue_to_pr_no_effect'}:Path(%r).write_text(a)"""
        % (str(closeout), str(wrong))
    )
    result = run_graph(tmp_path, body, "parent-closeout", path_id="issue_to_pr")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["close_existing_delivery"] == "succeeded"
        and st["issue_to_pr_subflow"] == "skipped"
    )
    assert closeout.exists() and not wrong.exists()
