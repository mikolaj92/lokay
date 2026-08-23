"""Native Fala proofs for bounded PR-conflict routes."""

from test_issue_triage_fala import base_effector, run_graph


def test_closed_conflict_routes_clear_and_ready(tmp_path):
    clear, ready = tmp_path / "clear", tmp_path / "ready"
    body = base_effector(
        """if a=='select_conflicting_pr':v.update(route='conflict',repo='a/b',pr=7)
if a=='close_conflicting_pr':v.update(route='closed',repo='a/b',pr=7)
if a=='select_conflict_close':v.update(route='closed',repo='a/b',pr=7)
if a=='resolve_conflict_issue':v.update(route='issue',repo='a/b',pr=7,issue=7)
if a=='select_conflict_issue':v.update(route='issue',repo='a/b',pr=7,issue=7)
if a=='clear_conflict_stuck_ledger':Path(%r).write_text('clear')
if a=='ready_issue_after_conflict':Path(%r).write_text('ready')
if a=='reduce_conflict_resolution':v.update(conflict_route='closed',conflict_closed=1)
if a=='record_conflict_resolution':v.update(route='closed',closed=1)
if a=='summarize_conflict_resolution':v['result']={'closed':1}"""
        % (str(clear), str(ready))
    )
    result = run_graph(tmp_path, body, "conflict-close", path_id="resolve_conflicts")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        clear.exists()
        and ready.exists()
        and status["ready_issue_after_conflict"] == "succeeded"
    )


def test_no_conflict_skips_all_effects(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector("""if a=='select_conflicting_pr':v['route']='none'
if a=='select_conflict_close':v['route']='none'
if a=='select_conflict_issue':v['route']='none'
if a in {'close_conflicting_pr','clear_conflict_stuck_ledger','ready_issue_after_conflict'}:Path(%r).write_text(a)
if a=='reduce_conflict_resolution':v['route']='none'
if a=='record_conflict_resolution':v.update(route='none',closed=0)
if a=='summarize_conflict_resolution':v['result']={'closed':0}""" % str(wrong))
    result = run_graph(tmp_path, body, "conflict-none", path_id="resolve_conflicts")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["close_conflicting_pr"]
        == status["ready_issue_after_conflict"]
        == "skipped"
    )
    assert not wrong.exists()
