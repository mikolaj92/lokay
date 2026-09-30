import json
from lokay.repair_boundary import (
    validate_output,
    select_initial,
    select_evidence,
    finalize,
    select_test,
    select_test_repair,
    finalize_tests,
)


def valid(verdict="repaired", kind=None):
    return json.dumps(
        {
            "verdict": verdict,
            "evidence_kind": kind,
            "summary": "done",
            "tests_run": ["pytest"],
            "residual_risk": "none",
        }
    )


def test_valid_repaired():
    assert validate_output(valid())["decision"]["verdict"] == "repaired"


def test_unknown_and_missing_kind_fail_closed():
    assert validate_output('{"verdict":"repaired","x":1}')["route"] == "retry"
    assert validate_output(valid("needs_evidence"))["route"] == "retry"


def test_invalid_retry_is_bounded():
    assert (
        select_initial(validate_output("bad"), validate_output(valid()))["route"]
        == "repaired"
    )
    assert (
        select_initial(validate_output("bad"), validate_output("bad"))["route"]
        == "fail_closed"
    )


def test_one_evidence_round():
    initial = select_initial(
        validate_output(valid("needs_evidence", "test_contract")), {}
    )
    assert initial["evidence_kind"] == "test_contract"
    assert (
        finalize(initial, select_evidence(initial, validate_output(valid())))["route"]
        == "repaired"
    )
    assert (
        select_evidence(
            initial, validate_output(valid("needs_evidence", "pr_metadata"))
        )["route"]
        == "fail_closed"
    )


def test_undeclared_repair_test_does_not_publish():
    skipped = select_test(
        {"ok": True, "skipped": True, "tested": False, "reason": "no_declared_test"}
    )
    assert skipped["route"] == "fail"
    assert finalize_tests(skipped, {"route": "not_applicable"})["route"] == "terminal"


def test_test_repair_is_bounded():
    red = select_test({"ok": True, "tested": True, "recorded_red": True})
    green = select_test({"ok": True, "tested": True})
    assert red["route"] == "fail" and green["route"] == "pass"
    failed_repair = select_test_repair(red, validate_output(valid()))
    assert failed_repair["route"] == "repaired"
    assert select_test_repair(green, validate_output(valid()))["route"] == "not_applicable"
    skipped = select_test({"ok": True, "tested": False, "skipped": True})
    assert skipped["route"] == "fail"
    assert select_test_repair(skipped, {})["route"] == "terminal"
    assert select_test_repair(red, {})["route"] == "terminal"
    assert finalize_tests(red, green)["route"] == "publish"
    assert finalize_tests(red, red)["route"] == "terminal"
    assert finalize_tests(red, {"route": "not_applicable"})["route"] == "terminal"
    assert finalize_tests(green, {"route": "not_applicable"})["route"] == "publish"
    assert finalize_tests({"route": "not_applicable"}, {"route": "not_applicable"})["route"] == "terminal"
    assert finalize_tests({"route": "not_applicable"}, green)["route"] == "terminal"
