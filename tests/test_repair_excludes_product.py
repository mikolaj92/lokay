"""A selected carrier repair closes every product department in the same pass."""

from lokay.organ.departments_boundary import handle_departments


REPAIR = {"select_self_repair_department": {"route": "run"}}


def test_repair_closes_issue_triage():
    out = handle_departments("select_issue_triage_department", {}, REPAIR, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "self_repair_selected"


def test_repair_closes_executor():
    out = handle_departments("select_executor_department", {}, REPAIR, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "self_repair_selected"


def test_repair_closes_pr_triage():
    out = handle_departments("select_pr_triage_department", {}, REPAIR, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "self_repair_selected"


def test_repair_closes_pr_repair():
    out = handle_departments("select_pr_repair_department", {}, REPAIR, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "self_repair_selected"


def test_product_still_runs_when_repair_skips():
    up = {"select_self_repair_department": {"route": "skip"}}
    out = handle_departments("select_issue_triage_department", {}, up, {})
    assert out is not None
    assert out["route"] == "run"
