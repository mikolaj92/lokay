"""Dry-run does not enter the self-repair graph."""

from lokay.organ.daemon_entry_boundary import handle_daemon_entry
from lokay.organ.departments_boundary import handle_departments
from lokay.proc import invoke_self_repair
from lokay.proc import run_initial_self_repair
from lokay.proc import run_self_repair_department


INCIDENT = {"route": "run", "fingerprint": "did_not_move", "incident_url": "u"}


def test_department_dry_run_skips_self_repair_graph(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("dry-run entered self-repair graph")

    monkeypatch.setattr(run_self_repair_department, "run_path", boom)
    out = handle_departments(
        "run_self_repair_department", {"live": False, "config_path": ""}, {}, {}
    )
    assert out is not None
    assert out["route"] == "skipped"
    assert out["reason"] == "dry_run"


def test_invoke_dry_run_skips_selected_incident(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("dry-run entered self-repair graph")

    monkeypatch.setattr(invoke_self_repair, "run_self_repair", boom)
    out = handle_departments(
        "invoke_self_repair",
        {"live": False},
        {"open_self_repair_incident": INCIDENT},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"


def test_daemon_entry_dry_run_skips_initial_repair(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("dry-run entered self-repair graph")

    monkeypatch.setattr(run_initial_self_repair, "run_self_repair", boom)
    out = handle_daemon_entry(
        "run_initial_self_repair",
        {"live": False, "config_path": "cfg"},
        {"classify_daemon_preflight": {"preflight": {"ok": False}}},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"
