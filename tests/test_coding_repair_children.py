"""Small atoms for the extracted coding and local-repair children."""

from lokay.organ.common import _require_test_local
from lokay.proc.coding_execution_terminal import terminal as coding_terminal
from lokay.proc.local_repair_terminal import terminal as repair_terminal
from lokay.proc.prepare_coding_request import prepare as prepare_coding
from lokay.proc.prepare_local_repair_request import prepare as prepare_repair


def test_prepare_coding_request_keeps_issue_and_localize():
    out = prepare_coding(
        worktree="/w",
        repo="o/r",
        issue=7,
        issue_raw={"title": "x"},
        localize={"paths": ["a.py"]},
        branch="ai/fix/7",
        live=False,
    )
    assert out["ok"] is True
    assert out["issue_raw"]["number"] == 7
    assert out["localize"]["paths"] == ["a.py"]


def test_coding_terminal_lifts_route_for_parent_when():
    out = coding_terminal(
        {"route": "implemented", "decision": {"verdict": "implemented"}},
        {},
    )
    assert out["route"] == "implemented"
    assert out["result"]["route"] == "implemented"


def test_local_repair_terminal_pass_after_green_recheck():
    out = repair_terminal(
        {"route": "repaired", "decision": {"verdict": "implemented"}},
        {"route": "pass"},
    )
    assert out["route"] == "pass" and out["passed"] is True


def test_require_test_local_finalize_publish_without_probe():
    assert (
        _require_test_local({"finalize_local_tests": {"ok": True, "route": "publish"}})
        is None
    )


def test_require_test_local_missing_finalize_and_probe():
    refused = _require_test_local({})
    assert refused["reason"] == "test_local_missing"


def test_require_test_local_accepts_execution_node_and_repair_child():
    assert (
        _require_test_local({"test_local_execution": {"ok": True, "tested": True}})
        is None
    )
    assert (
        _require_test_local(
            {
                "test_local_execution": {
                    "ok": True,
                    "tested": True,
                    "recorded_red": True,
                    "passed": False,
                },
                "local_repair_execution": {"route": "pass", "passed": True},
            }
        )
        is None
    )
    refused = _require_test_local(
        {
            "test_local_execution": {
                "ok": True,
                "tested": True,
                "recorded_red": True,
                "passed": False,
            },
            "local_repair_execution": {"route": "terminal"},
        }
    )
    assert refused["reason"] == "test_local_recheck_failed"
