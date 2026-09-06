"""Completed department evidence must reach the real pass receipt (#920)."""

import pytest

from lokay.organ.factory import handle_factory
from lokay.pass_receipt import read_pass_receipt
from lokay.passkit import io as pass_io
from lokay.proc.select_repair_route import classify
from test_departments_fala import _factory_path
from test_record_pass import _begin


@pytest.mark.parametrize("delivery", ["executor", "pr_triage", "none"])
def test_authored_receipt_receives_completed_delivery(tmp_path, delivery):
    pass_dir = _begin(tmp_path)
    pass_io.write_json(pass_io.tick_path(pass_dir), {
        "ok": True, "health": "hosted", "idle": False, "progress": 0,
    })
    outputs = {
        "factory_begin": {"pass_dir": str(pass_dir)},
        "factory_begin_host_gate": {"route": "begin"},
        "run_issue_triage_department": {"result": {"launched": None}},
        "run_executor_department": {"result": {
            "launched": "started" if delivery == "executor" else None,
        }},
        "run_pr_triage_department": {"result": {
            "triage": {"merged": delivery == "pr_triage"},
        }},
    }
    node = next(n for n in _factory_path()["effectors"] if n["id"] == "record_pass")
    # Fala only passes explicitly authored conduction, not every prior result.
    upstream = {name: outputs.get(name, {}) for name in node["conduction"]}
    ctx = {
        "cfg": [], "live": [], "repo": "local/factory", "issue_number": None,
        "pr_number": None, "repair_mode": False, "branch": None,
    }
    out = handle_factory("record_pass", {}, upstream, ctx)
    expected = {"executor": "new_pr", "pr_triage": "merge", "none": "none"}
    assert out is not None
    assert out["outcome"] == expected[delivery]
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert classify(receipt)["reason"] == (
        "unconfirmed_stall" if delivery == "none" else "moved_forward"
    )


def test_receipt_waits_for_department_results_not_cleanup():
    node = next(n for n in _factory_path()["effectors"] if n["id"] == "record_pass")
    for name in ("self_repair", "issue_triage", "executor", "pr_triage", "pr_repair"):
        assert f"run_{name}_department" in node["conduction"]
    assert "reap_stale_worktrees" not in node["conduction"]