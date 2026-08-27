"""Closed issue-triage state boundary."""
from lokay.issue_triage_boundary import resolve_candidate, resolve_hard_facts, select_evidence, select_initial, validate_output
from lokay.proc.apply_issue_skip import apply as apply_skip

def issue(**extra):
    value={"repo":"a/b","number":7,"title":"Implement useful feature","body":"A sufficiently detailed body with clear acceptance criteria.","labels":[],"assignees":["mikolaj92"],"url":"u","state":"OPEN","author":"mikolaj92"}; value.update(extra); return value

def test_candidate_skip_is_execution_not_semantic_reinterpretation():
    out=resolve_candidate(issue(labels=["ai:ready"]),ready_label="ai:ready",blocked_label="ai:blocked",needs_feedback_label="ai:needs-feedback")
    assert out == {"ok":True,"route":"skip","reason":"already_decided"}

def test_hard_duplicate_closes_before_agent():
    out=resolve_hard_facts(issue(),{"route":"evaluate"},{"merged_prs":[]},{"covering_prs":[{"number":9,"state":"OPEN"}]})
    assert out["route"] == "terminal" and out["decision"]["verdict"] == "close"

def test_invalid_json_gets_one_retry_then_human():
    first=validate_output("not json"); assert first["route"] == "retry"
    retry=validate_output("still invalid")
    out=select_initial({"route":"agent"},first,retry)
    assert out["decision"]["verdict"] == "needs_human"

def test_closed_schema_rejects_unknown_and_non_scalar_evidence_request():
    out=validate_output('{"verdict":"ready","route":"merge"}')
    assert out["route"] == "retry" and "unknown" in out["validation_error"]
    out=validate_output('{"verdict":"needs_evidence","evidence_kind":"shell"}')
    assert out["route"] == "retry" and "evidence_kind" in out["validation_error"]

def test_evidence_request_routes_directly_and_second_request_is_terminal():
    first=validate_output('{"verdict":"needs_evidence","evidence_kind":"named_paths","evidence":[]}')
    selected=select_initial({"route":"agent"},first,{})
    assert selected["route"] == "evidence" and selected["evidence_kind"] == "named_paths"
    again=validate_output('{"verdict":"needs_evidence","evidence_kind":"repo_shape","evidence":[]}')
    final=select_evidence(selected,again)
    assert final["decision"] == {"verdict":"needs_human","reason":"issue_evidence_exhausted"}


def test_agent_split_is_not_a_sito_verdict():
    out=validate_output('{"verdict":"split","reason":"too_large"}')
    assert out["route"] == "retry" and "verdict" in out["validation_error"]


def test_skip_leaf_records_nie_without_mutation():
    out=apply_skip(decision={"verdict":"skip","reason":"already_decided"})
    assert out == {"ok":True,"applied":False,"skipped":True,"verdict":"skip","reason":"already_decided"}


def test_preflight_hard_fact_stays_blocked_without_agent_or_manual_rewrite():
    data=issue(title="Preflight failure xyz",body="<!-- lokay-preflight:abcdef --> sufficient incident detail")
    out=resolve_hard_facts(data,{"route":"evaluate"},{"merged_prs":[]},{"covering_prs":[]})
    assert out["route"] == "terminal"
    assert out["decision"]["verdict"] == "blocked"
