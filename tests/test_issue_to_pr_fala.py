"""Native Fala proofs for the thin issue delivery parent and extracted children."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def test_valid_implementation_skips_repair_then_publishes(tmp_path):
    pushed = tmp_path / "push"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='coding_execution':v.update(route='implemented',decision={'verdict':'implemented'})
if a=='test_local_execution':v.update(tested=True)
if a=='select_local_test':v['route']='pass'
if a=='finalize_local_tests':v['route']='publish'
if a=='push':Path(%r).write_text('ran')
if a=='local_repair_execution':Path(%r).write_text(a)"""
        % (str(pushed), str(wrong))
    )
    result = run_graph(tmp_path, body, "implemented", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "succeeded" and pushed.exists() and not wrong.exists()


def test_human_coding_skips_publish(tmp_path):
    pushed = tmp_path / "push"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='coding_execution':v.update(route='human',decision={'verdict':'needs_human'})
if a=='push':Path(%r).write_text('ran')"""
        % str(pushed)
    )
    result = run_graph(tmp_path, body, "human", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["test_local_execution"] == "skipped"
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "skipped" and not pushed.exists()


def test_red_test_runs_local_repair_then_terminal(tmp_path):
    repair = tmp_path / "repair"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='coding_execution':v.update(route='implemented',decision={'verdict':'implemented'})
if a=='test_local_execution':v.update(tested=True,recorded_red=True)
if a=='select_local_test':v['route']='fail'
if a=='local_repair_execution':Path(%r).write_text('ran');v.update(route='terminal')
if a=='finalize_local_tests':v['route']='repair_terminal'"""
        % str(repair)
    )
    result = run_graph(tmp_path, body, "repair", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["local_repair_execution"] == "succeeded"
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


def test_coding_execution_skips_retry_and_evidence(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='prepare_coding_request':v.update(worktree='/w',localize={'paths':['a.py']})
if a=='run_agent':v['stdout']='ok'
if a=='validate_coding_result':v.update(route='valid',decision={'verdict':'implemented'})
if a=='select_coding_result':v.update(route='implemented',evidence_kind='none',decision={'verdict':'implemented'})
if a=='select_evidence_coding':v['route']='not_applicable'
if a=='finalize_coding_result':v.update(route='implemented',decision={'verdict':'implemented'})
if a in {'coding_retry_agent','evidence_coding_agent'}:Path(%r).write_text(a)"""
        % str(wrong)
    )
    result = run_graph(tmp_path, body, "coding-ok", path_id="coding_execution")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["coding_retry_agent"] == "skipped"
    assert st["evidence_coding_agent"] == "skipped"
    assert st["coding_execution_terminal"] == "succeeded"
    assert not wrong.exists()


def test_coding_execution_invalid_json_runs_one_retry(tmp_path):
    retry = tmp_path / "retry"
    body = base_effector(
        """if a=='prepare_coding_request':v.update(worktree='/w',localize={'paths':['a.py']})
if a=='validate_coding_result':v.update(route='retry',validation_error='bad')
if a=='coding_retry_agent':Path(%r).write_text('ran')
if a=='validate_coding_retry':v.update(route='valid',decision={'verdict':'needs_human'})
if a=='select_coding_result':v.update(route='human',evidence_kind='none',decision={'verdict':'needs_human'})
if a=='select_evidence_coding':v['route']='not_applicable'
if a=='finalize_coding_result':v.update(route='human',decision={'verdict':'needs_human'})"""
        % str(retry)
    )
    result = run_graph(tmp_path, body, "coding-retry", path_id="coding_execution")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["coding_retry_agent"] == "succeeded"
    assert st["coding_manual"] == "succeeded"
    assert retry.exists()


def test_coding_execution_runs_only_selected_collector(tmp_path):
    chosen = tmp_path / "chosen"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='prepare_coding_request':v.update(worktree='/w',localize={'paths':['a.py']})
if a=='validate_coding_result':v.update(route='valid',decision={'verdict':'needs_evidence','evidence_kind':'test_contract'})
if a=='select_coding_result':v.update(route='evidence',evidence_kind='test_contract',decision={'verdict':'needs_evidence'})
if a=='collect_coding_test_contract':Path(%r).write_text('ran')
if a in {'collect_coding_issue_snapshot','collect_coding_repo_structure','collect_coding_localized_diff'}:Path(%r).write_text(a)
if a=='validate_evidence_coding':v.update(route='valid',decision={'verdict':'needs_human'})
if a=='select_evidence_coding':v.update(route='human',decision={'verdict':'needs_human'})
if a=='finalize_coding_result':v.update(route='human',decision={'verdict':'needs_human'})"""
        % (str(chosen), str(wrong))
    )
    result = run_graph(tmp_path, body, "coding-evidence", path_id="coding_execution")
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


def test_local_repair_invalid_json_is_terminal(tmp_path):
    repair = tmp_path / "repair"
    body = base_effector(
        """if a=='prepare_local_repair_request':v.update(worktree='/w',first_test={'recorded_red':True})
if a=='repair_agent':Path(%r).write_text('ran')
if a=='validate_repair_result':v['route']='retry'
if a=='select_repair_result':v['route']='terminal'
if a=='select_local_test_recheck':v['route']='not_applicable'"""
        % str(repair)
    )
    result = run_graph(tmp_path, body, "repair-terminal", path_id="local_repair_execution")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["repair_agent"] == "succeeded"
    assert st["commit_repair"] == "skipped"
    assert st["test_local_recheck"] == "skipped"
    assert st["local_repair_terminal"] == "succeeded"
    assert repair.exists()
