from lokay.coding_boundary import (
    validate_output,
    select_initial,
    select_evidence,
    finalize,
    select_test,
    finalize_tests,
    select_repair,
)


def valid(verdict="implemented", kind=None):
    import json

    return json.dumps(
        {
            "verdict": verdict,
            "evidence_kind": kind,
            "summary": "done",
            "tests_run": ["pytest"],
            "residual_risk": "none",
        }
    )


def test_closed_schema_accepts_implemented():
    out = validate_output(valid())
    assert out["route"] == "valid" and out["decision"]["verdict"] == "implemented"


def test_closed_schema_rejects_unknown_and_missing_evidence_kind():
    assert validate_output('{"verdict":"implemented","surprise":1}')["route"] == "retry"
    assert validate_output(valid("needs_evidence"))["route"] == "retry"


def test_one_invalid_retry_selects_valid_retry():
    first = validate_output("no")
    retry = validate_output(valid())
    assert select_initial(first, retry)["route"] == "implemented"


def test_second_invalid_fails_closed():
    out = select_initial(validate_output("no"), validate_output("still no"))
    assert out["route"] == "human" and out["decision"]["verdict"] == "needs_human"


def test_empty_localize_is_failed_not_invalid_json_retry():
    first = {"ok": True, "route": "empty", "reason": "localize_timeout"}
    retry = validate_output(valid())
    out = select_initial(first, retry)
    assert out["route"] == "failed"
    assert out["reason"] == "localize_timeout"


def test_closed_evidence_round_can_implement():
    initial = select_initial(
        validate_output(valid("needs_evidence", "repo_structure")), {}
    )
    assert (
        initial["route"] == "evidence" and initial["evidence_kind"] == "repo_structure"
    )
    selected = select_evidence(initial, validate_output(valid()))
    assert finalize(initial, selected)["route"] == "implemented"


def test_second_evidence_request_fails_closed():
    initial = {"route": "evidence"}
    again = validate_output(valid("needs_evidence", "localized_diff"))
    assert select_evidence(initial, again)["route"] == "human"


def test_physical_tests_route_once_to_repair():
    red = select_test({"ok": True, "recorded_red": True, "tested": True})
    green = select_test({"ok": True, "tested": True})
    assert red["route"] == "fail" and green["route"] == "pass"
    assert finalize_tests(red, green)["route"] == "publish"
    assert finalize_tests(red, red)["route"] == "repair_terminal"
    assert finalize_tests(red, red, applicable=False)["route"] == "not_applicable"
    assert select_test({}, applicable=False)["route"] == "not_applicable"


def test_repair_requires_valid_implemented_result():
    assert select_repair(validate_output(valid()))["route"] == "repaired"
    assert select_repair(validate_output("bad"))["route"] == "terminal"
