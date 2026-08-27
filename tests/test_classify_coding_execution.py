"""Failed or empty coding_execution is a classified parent route."""

from __future__ import annotations

import json

from lokay.proc.classify_coding_execution import classify, main
from lokay.proc.coding_execution_subflow import run as run_coding
from test_issue_to_pr_fala import simulate_path


def test_implemented_child_keeps_route():
    out = classify(
        {
            "ok": True,
            "route": "implemented",
            "decision": {"verdict": "implemented"},
            "evidence_kind": "none",
        }
    )
    assert out["ok"] is True
    assert out["route"] == "implemented"
    assert out["decision"]["verdict"] == "implemented"


def test_failed_empty_child_is_empty_route_not_process_failed():
    out = classify(
        {
            "ok": False,
            "error": "sqlite.fire failed to step query",
            "fala": {"run_status": "failed"},
        }
    )
    assert out["ok"] is True
    assert out["route"] == "empty"
    assert "sqlite.fire" in str(out["reason"])


def test_missing_child_is_empty_route():
    out = classify(None)
    assert out["ok"] is True and out["route"] == "empty"
    assert out["reason"] == "coding_execution_empty"


def test_empty_coding_route_lets_parent_skip_relocalize():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "coding_execution": {"route": "empty"},
        },
    )
    assert st["coding_execution"] == "succeeded"
    assert st["relocalize_off_goal"] == "skipped"
    assert st["test_local_execution"] == "skipped"
    assert st["push"] == "skipped"


def test_subflow_failed_nested_fala_still_yields_parent_route(monkeypatch):
    def boom(**_kwargs):
        return {
            "ok": False,
            "error": "sqlite.fire failed to step query",
            "route": None,
        }

    monkeypatch.setattr("lokay.proc.coding_execution_subflow.run_path", boom)
    out = run_coding(config_path=None, live=False, extra_inputs={"repo": "a/b", "issue": 1})
    assert out["ok"] is True
    assert out["route"] == "empty"
    assert "error" not in out


def test_cli_classifies_failed_child(capsys):
    code = main(
        [
            "--child-json",
            json.dumps({"ok": False, "reason": "nested_fala_empty"}),
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["route"] == "empty"
    assert out["reason"] == "nested_fala_empty"
