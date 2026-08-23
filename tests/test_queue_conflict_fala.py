"""Native Fala proofs for authoritative queue-conflict routes."""

from test_issue_triage_fala import base_effector, run_graph


def test_valid_ready_skips_retry_and_mutations(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='select_queue_conflict_candidate':v.update(route='candidate',repo='a/b',issue=7,candidate={'number':7})
if a=='check_queue_covering_pr':v.update(route='agent',repo='a/b',issue=7,candidate={'number':7})
if a=='select_queue_conflict_gate':v.update(route='agent',repo='a/b',issue=7,candidate={'number':7})
if a=='validate_queue_conflict':v.update(route='valid',decision={'outcome':'ready','reason':'agent_ready','add_tracker':False})
if a=='select_queue_conflict_outcome':v.update(route='ready',repo='a/b',issue=7,decision={'outcome':'ready','reason':'agent_ready','add_tracker':False})
if a=='select_queue_tracker':v['route']='none'
if a in {'queue_conflict_retry_agent','remove_queue_ready_label','add_queue_tracker_label'}:Path(%r).write_text(a)
if a=='record_queue_conflict':v['route']='ready'
if a=='summarize_queue_conflict':v['result']={'kept':1}"""
        % str(wrong)
    )
    result = run_graph(tmp_path, body, "queue-ready", path_id="queue_conflict")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert status["queue_conflict_retry_agent"] == "skipped"
    assert (
        status["remove_queue_ready_label"]
        == status["add_queue_tracker_label"]
        == "skipped"
    )
    assert not wrong.exists()


def test_invalid_json_runs_once_then_close_effects(tmp_path):
    retry, remove, tracker = (
        tmp_path / "retry",
        tmp_path / "remove",
        tmp_path / "tracker",
    )
    body = base_effector(
        """if a=='select_queue_conflict_candidate':v.update(route='candidate',repo='a/b',issue=7,candidate={'number':7})
if a=='check_queue_covering_pr':v.update(route='agent',repo='a/b',issue=7,candidate={'number':7})
if a=='select_queue_conflict_gate':v.update(route='agent',repo='a/b',issue=7,candidate={'number':7})
if a=='validate_queue_conflict':v.update(route='retry',validation_error='exact error')
if a=='queue_conflict_retry_agent':Path(%r).write_text('one')
if a=='validate_queue_conflict_retry':v.update(route='valid',decision={'outcome':'close','reason':'epic','add_tracker':True})
if a=='select_queue_conflict_outcome':v.update(route='close',repo='a/b',issue=7,decision={'outcome':'close','reason':'epic','add_tracker':True})
if a=='select_queue_tracker':v['route']='tracker'
if a=='remove_queue_ready_label':Path(%r).write_text('remove')
if a=='add_queue_tracker_label':Path(%r).write_text('tracker')
if a=='record_queue_conflict':v['route']='close'
if a=='summarize_queue_conflict':v['result']={'demoted':1}"""
        % (str(retry), str(remove), str(tracker))
    )
    result = run_graph(tmp_path, body, "queue-close", path_id="queue_conflict")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert retry.exists() and remove.exists() and tracker.exists()
    assert (
        status["queue_conflict_retry_agent"]
        == status["add_queue_tracker_label"]
        == "succeeded"
    )


def test_covering_pr_bypasses_both_agents(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='select_queue_conflict_candidate':v.update(route='candidate',repo='a/b',issue=7,candidate={'number':7})
if a=='check_queue_covering_pr':v.update(route='covered',repo='a/b',issue=7,candidate={'number':7},decision={'outcome':'close','reason':'covered','add_tracker':False})
if a=='select_queue_conflict_gate':v.update(route='covered',repo='a/b',issue=7,candidate={'number':7},decision={'outcome':'close','reason':'covered','add_tracker':False})
if a in {'validate_queue_conflict','validate_queue_conflict_retry'}:v['route']='not_applicable'
if a in {'queue_conflict_agent','queue_conflict_retry_agent'}:Path(%r).write_text(a)
if a=='select_queue_conflict_outcome':v.update(route='close',repo='a/b',issue=7,decision={'outcome':'close','reason':'covered','add_tracker':False})
if a=='select_queue_tracker':v['route']='none'
if a=='record_queue_conflict':v['route']='close'
if a=='summarize_queue_conflict':v['result']={'demoted':1}"""
        % str(wrong)
    )
    result = run_graph(tmp_path, body, "queue-cover", path_id="queue_conflict")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["queue_conflict_agent"]
        == status["queue_conflict_retry_agent"]
        == "skipped"
    )
    assert not wrong.exists()


def test_no_candidate_skips_semantic_and_mutation_nodes(tmp_path):
    wrong = tmp_path / "wrong"
    body = base_effector("""if a=='select_queue_conflict_candidate':v['route']='none'
if a=='select_queue_conflict_gate':v['route']='none'
if a in {'validate_queue_conflict','validate_queue_conflict_retry'}:v['route']='not_applicable'
if a in {'queue_conflict_agent','queue_conflict_retry_agent','remove_queue_ready_label','add_queue_tracker_label'}:Path(%r).write_text(a)
if a=='select_queue_conflict_outcome':v['route']='none'
if a=='select_queue_tracker':v['route']='none'
if a=='record_queue_conflict':v['route']='none'
if a=='summarize_queue_conflict':v['result']={'kept':0}""" % str(wrong))
    result = run_graph(tmp_path, body, "queue-none", path_id="queue_conflict")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["queue_conflict_agent"]
        == status["remove_queue_ready_label"]
        == "skipped"
    )
    assert not wrong.exists()
