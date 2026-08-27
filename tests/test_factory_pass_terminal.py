"""factory_pass_terminal lifts only record_pass. It does not idle-skip."""

from lokay.organ.factory import handle_factory
from lokay.proc.factory_pass_terminal import terminal


def _ctx() -> dict:
    return {
        "cfg": None,
        "live": False,
        "repo": "o/r",
        "issue_number": 0,
        "pr_number": 0,
        "repair_mode": False,
        "branch": "",
    }


def test_terminal_lifts_record_pass() -> None:
    out = terminal({"result": {"ok": True, "health": "progress", "lane": "product"}})
    assert out["result"]["lane"] == "product"
    assert out["result"]["health"] == "progress"


def test_terminal_lifts_idle_lane_from_record_pass_only() -> None:
    out = terminal(
        {"result": {"ok": True, "health": "idle", "lane": "idle", "idle": True}}
    )
    assert out == {
        "ok": True,
        "result": {"ok": True, "health": "idle", "lane": "idle", "idle": True},
    }


def test_terminal_missing_record_pass_is_not_idle() -> None:
    out = terminal({})
    assert out == {
        "ok": True,
        "result": {"ok": False, "health": "record_pass_result_missing"},
    }


def test_organ_lifts_record_pass_and_ignores_idle_upstreams() -> None:
    out = handle_factory(
        "factory_pass_terminal",
        {},
        {
            "classify_factory_idle": {
                "route": "idle",
                "reason": "recent_empty_survey",
            },
            "record_factory_idle": {
                "result": {"ok": True, "health": "idle", "lane": "idle"},
            },
            "record_pass": {
                "result": {"ok": True, "health": "progress", "lane": "product"},
            },
        },
        _ctx(),
    )
    assert out == {
        "ok": True,
        "result": {"ok": True, "health": "progress", "lane": "product"},
    }


def test_organ_empty_record_pass_does_not_idle_skip() -> None:
    out = handle_factory(
        "factory_pass_terminal",
        {},
        {
            "classify_factory_idle": {"route": "idle", "reason": "recent_empty_survey"},
            "record_factory_idle": {
                "result": {"ok": True, "health": "idle", "lane": "idle"},
            },
        },
        _ctx(),
    )
    assert out == {
        "ok": True,
        "result": {"ok": False, "health": "record_pass_result_missing"},
    }
