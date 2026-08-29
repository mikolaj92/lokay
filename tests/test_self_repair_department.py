"""self_repair department: only after no movement; leftover skip is not a stall."""

import tomllib
from pathlib import Path

from lokay.proc.invoke_self_repair import run as invoke
from lokay.proc.select_self_repair_department import leftover_gate, select


def _path(path_id: str) -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == path_id)


def test_leftover_gate_is_not_a_stall() -> None:
    assert leftover_gate(leftover_skip=True) == {
        "ok": True,
        "route": "skip",
        "reason": "leftover_skip",
    }
    assert leftover_gate(leftover_skip=False)["route"] == "run"


def test_select_skips_leftover_even_when_last_pass_did_not_move() -> None:
    assert select(enabled=True, moved_forward=False, leftover_skip=True) == {
        "ok": True,
        "route": "skip",
        "reason": "leftover_skip",
    }
    assert select(enabled=True, moved_forward=False)["route"] == "run"
    assert select(enabled=False, moved_forward=False, leftover_skip=True) == {
        "ok": True,
        "route": "skip",
        "reason": "self_repair_disabled",
    }


def test_disabled_never_routes_run() -> None:
    assert select(enabled=False, moved_forward=False)["route"] == "skip"
    assert select(enabled=False, moved_forward=True)["reason"] == "self_repair_disabled"


def test_invoke_does_not_start_without_incident() -> None:
    assert invoke({"route": "skip", "reason": "incident_unavailable"}, config_path=None) == {
        "ok": True,
        "route": "skip",
        "department": "self_repair",
        "reason": "incident_unavailable",
    }


def test_department_graph_is_two_blocks() -> None:
    ids = [str(node["id"]) for node in _path("self_repair_department")["effectors"]]
    assert ids == ["open_self_repair_incident", "invoke_self_repair"]
    by_id = {node["id"]: node for node in _path("self_repair_department")["effectors"]}
    assert by_id["invoke_self_repair"]["when"] == {
        "upstream": "open_self_repair_incident",
        "path": "route",
        "equals": "run",
    }


def test_parent_factory_still_has_the_named_slot() -> None:
    ids = [str(node["id"]) for node in _path("factory_pass")["effectors"]]
    assert "select_self_repair_department" in ids
    assert "run_self_repair_department" in ids
    assert ids.index("select_self_repair_department") < ids.index(
        "select_issue_triage_department"
    )
