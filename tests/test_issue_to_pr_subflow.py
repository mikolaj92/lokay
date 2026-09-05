"""issue_to_pr_subflow: classified route, never process.failed / no route."""

from lokay.organ.coding_boundary import handle_coding_boundary
from lokay.proc.classify_issue_to_pr_subflow import classify, failed
from lokay.proc.issue_to_pr_subflow import invoke
from lokay.proc.select_local_test import select


FIRE_STEP = "sqlite.fire: failed to step query"
SOURCE = "condition_source_not_succeeded"


def test_failed_helper_is_succeeded_classified_route():
    out = failed(FIRE_STEP)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["result"]["route"] == "failed"
    assert FIRE_STEP in str(out["error"])


def test_skipped_select_local_test_is_skip():
    assert select({}, applicable=False) == {"ok": True, "route": "skip"}
    assert select({"ok": True, "tested": True}, applicable=True)["route"] == "pass"


def test_delivery_throw_yields_route(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError(SOURCE)

    monkeypatch.setattr("lokay.proc.issue_to_pr_subflow.run_path", boom)
    out = invoke(config_path=None, repo="Temida/Temida", issue=64, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert SOURCE in str(out["error"])


def test_delivery_not_ok_yields_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.issue_to_pr_subflow.run_path",
        lambda **_k: {"ok": False, "error": SOURCE},
    )
    out = invoke(config_path=None, repo="Temida/Temida", issue=64, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_empty_delivery_yields_classified_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.issue_to_pr_subflow.run_path",
        lambda **_k: {"ok": True, "route": "", "result": {}},
    )
    out = invoke(config_path=None, repo="Temida/Temida", issue=64, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_successful_delivery_without_pr_is_no_effect():
    out = classify({"ok": True, "result": {"delivered": False, "stopped": True}})
    assert out["ok"] is True
    assert out["route"] == "no_effect"


def test_successful_authored_delivery_terminal_without_pr_is_no_effect():
    out = classify(
        {
            "ok": True,
            "branch": "ai/fix/84-product-host",
            "pr": None,
            "delivered": False,
        }
    )
    assert out["ok"] is True
    assert out["route"] == "no_effect"
    assert out["branch"] == "ai/fix/84-product-host"


def test_successful_delivery_with_pr_is_deliver():
    out = classify({"ok": True, "pr": 12, "delivered": True, "result": {"pr": 12}})
    assert out["ok"] is True
    assert out["route"] == "deliver"


def test_fire_failure_does_not_mark_issue_to_pr_adapter_failed(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.issue_to_pr_subflow.run_path",
        lambda **_k: {"ok": False, "error": SOURCE},
    )
    out = handle_coding_boundary(
        "issue_to_pr_subflow",
        {"live": False, "repo": "Temida/Temida", "issue": 64},
        {},
        {"repo": "Temida/Temida", "issue_number": 64},
    )
    assert out is not None
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out.get("status") != "failed"
    assert out.get("_exit", 0) == 0
    assert SOURCE in str(out.get("error") or "")


def test_select_local_test_skip_when_coding_is_not_implemented():
    out = handle_coding_boundary(
        "select_local_test",
        {},
        {"coding_execution": {"route": "failed"}, "test_local_execution": {}},
        {"repo": "Temida/Temida", "issue_number": 64},
    )
    assert out == {"ok": True, "route": "skip"}
