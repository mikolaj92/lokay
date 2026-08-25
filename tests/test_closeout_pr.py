"""Contracts for authored PR-closeout Unix atoms and subflows."""

from pathlib import Path
from lokay.passkit import io as pass_io


def _selected(**pr):
    return {
        "ok": True,
        "route": "closeout",
        "repo": "o/r",
        "pr": {
            "number": 7,
            "head_ref": "ai/fix/7-x",
            "mergeable": "MERGEABLE",
            "labels": [],
            **pr,
        },
        "repair_budget": 1,
        "policy": {
            "merge_enabled": True,
            "require_checks": False,
            "executor_enabled": True,
            "branch_prefix": "ai/fix/",
        },
    }


def test_manual_pr_gate_is_terminal():
    from lokay.proc.inspect_closeout_pr import inspect
    from lokay.proc.classify_closeout_gate import classify

    item = inspect(_selected(labels=["ai:needs-review"]))
    out = classify(item, {"route": "open_or_unknown"})
    assert out["route"] == "manual"


def test_conflicting_pr_gate_is_terminal():
    from lokay.proc.inspect_closeout_pr import inspect

    assert inspect(_selected(mergeable="CONFLICTING"))["route"] == "conflict"


def test_checks_route_waits():
    from lokay.proc.route_closeout_checks import route

    gate = {"inspected": _selected() | {"pr_number": 7, "head": "ai/fix/7-x"}}
    out = route(
        gate, {"route": "route", "checks": {"ok": True, "status": "pending"}}, live=True
    )
    assert (
        out["route"] == "final"
        and out["domain_route"] == "wait"
        and out["deltas"]["pending_checks"] == 1
    )


def test_checks_route_repairs_once():
    from lokay.proc.route_closeout_checks import route
    from lokay.proc.authorize_closeout_repair import authorize

    item = _selected() | {"pr_number": 7, "head": "ai/fix/7-x"}
    routed = route(
        {"inspected": item},
        {"route": "route", "checks": {"ok": True, "status": "failed"}},
        live=True,
    )
    assert (
        routed["route"] == "repair"
        and authorize({"inspected": item}, routed)["route"] == "repair"
    )


def test_closeout_catalog_overflow_fails_closed(tmp_path):
    from lokay.proc.prepare_pr_closeout import prepare

    pd = tmp_path / "pass"
    pd.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pd), {"repos": [f"o/r{i}" for i in range(31)]}
    )
    pass_io.write_json(pass_io.working_path(pd), {})
    assert prepare(pass_dir=str(pd), slot_count=30)["ok"] is False


def test_oil_closeout_empty_when_product_queue():
    from lokay.proc.select_pr_closeout_slot import select

    prepared = {
        "repos": ["mikolaj92/lokay", "a/product"],
        "prs_by_repo": {
            "mikolaj92/lokay": [{"number": 9, "headRefName": "ai/fix/1"}],
            "a/product": [{"number": 3, "headRefName": "ai/fix/2"}],
        },
        "ready_by_repo": {"a/product": [{"number": 4}]},
        "self_repo": "mikolaj92/lokay",
        "product_queue": True,
        "repair_budget": 1,
    }
    oil = select(prepared, {}, slot=1)
    product = select(prepared, {}, slot=2)
    assert oil["route"] == "empty" and oil["reason"] == "product_lane"
    assert product["route"] == "closeout" and product["repo"] == "a/product"


def test_one_open_pr_invariant_fails_closed():
    from lokay.proc.select_pr_closeout_slot import select

    prepared = {
        "repos": ["o/r"],
        "prs_by_repo": {"o/r": [{"number": 1}, {"number": 2}]},
        "repair_budget": 1,
    }
    out = select(prepared, {}, slot=1)
    assert out["route"] == "needs_human" and out["reason"] == "multiple_open_ai_prs"


def test_closeout_reducer_removes_merged_pr():
    from lokay.proc.reduce_pr_closeout import reduce_state

    working = {
        "actions": [],
        "progress": 0,
        "prs_by_repo": {"o/r": [{"number": 7, "labels": []}]},
    }
    row = {"repo": "o/r", "still_open": False, "progress": 1, "repair_budget": 1}
    out = reduce_state(prepared={"repair_budget": 1}, rows=[row], working=working)
    assert out["state"]["prs_by_repo"]["o/r"] == [] and out["state"]["progress"] == 1


def test_cli_surface_remains_wired():
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text()
    assert "lokay-closeout-pr" in text and "lokay-closeout-prs" in text
