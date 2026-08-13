"""Hermetic tests for lokay.proc.pi_budget. No live long process."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc import pi_budget


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_over_budget_when_running_past_budget():
    payload = pi_budget.check_pi_budget(
        42,
        budget_s=480,
        clock=lambda: 1000.0,
        started_at=lambda pid: 500.0,
    )
    assert payload["ok"] is True
    assert payload["over_budget"] is True
    assert payload["pid"] == 42
    assert payload["elapsed_s"] == 500.0
    assert payload["budget_s"] == 480


def test_within_budget_when_running():
    payload = pi_budget.check_pi_budget(
        7,
        budget_s=480,
        clock=lambda: 1000.0,
        started_at=lambda pid: 600.0,
    )
    assert payload["ok"] is True
    assert payload["over_budget"] is False
    assert payload["pid"] == 7
    assert payload["elapsed_s"] == 400.0
    assert payload["budget_s"] == 480


def test_not_running_is_not_over_budget():
    payload = pi_budget.check_pi_budget(
        99,
        budget_s=480,
        clock=lambda: 10_000.0,
        started_at=lambda pid: None,
    )
    assert payload["ok"] is True
    assert payload["over_budget"] is False
    assert payload["pid"] == 99
    assert payload["budget_s"] == 480


def test_default_budget_is_480():
    payload = pi_budget.check_pi_budget(
        1,
        clock=lambda: 481.0,
        started_at=lambda pid: 0.0,
    )
    assert payload["budget_s"] == pi_budget.DEFAULT_BUDGET_S == 480
    assert payload["over_budget"] is True
    assert payload["elapsed_s"] == 481.0


def test_at_budget_is_not_past():
    payload = pi_budget.check_pi_budget(
        3,
        budget_s=480,
        clock=lambda: 480.0,
        started_at=lambda pid: 0.0,
    )
    assert payload["over_budget"] is False
    assert payload["elapsed_s"] == 480.0


def test_cli_over_budget_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(pi_budget, "process_started_at", lambda pid: 100.0)
    monkeypatch.setattr(pi_budget.time, "time", lambda: 700.0)
    code = pi_budget.main(["--pid", "42"])
    assert code == 2
    out = _payload(capsys)
    assert out["over_budget"] is True
    assert out["pid"] == 42
    assert out["elapsed_s"] == 600.0
    assert out["budget_s"] == 480


def test_cli_within_budget_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(pi_budget, "process_started_at", lambda pid: 100.0)
    monkeypatch.setattr(pi_budget.time, "time", lambda: 200.0)
    code = pi_budget.main(["--pid", "8", "--budget", "480"])
    assert code == 0
    out = _payload(capsys)
    assert out["over_budget"] is False
    assert out["pid"] == 8
    assert out["elapsed_s"] == 100.0
    assert out["budget_s"] == 480


def test_cli_not_running_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(pi_budget, "process_started_at", lambda pid: None)
    monkeypatch.setattr(pi_budget.time, "time", lambda: 999.0)
    code = pi_budget.main(["--pid", "1234"])
    assert code == 0
    out = _payload(capsys)
    assert out["over_budget"] is False
    assert out["pid"] == 1234


def test_cli_honors_budget_flag(monkeypatch, capsys):
    monkeypatch.setattr(pi_budget, "process_started_at", lambda pid: 0.0)
    monkeypatch.setattr(pi_budget.time, "time", lambda: 50.0)
    code = pi_budget.main(["--pid", "5", "--budget", "10"])
    assert code == 2
    out = _payload(capsys)
    assert out["over_budget"] is True
    assert out["elapsed_s"] == 50.0
    assert out["budget_s"] == 10


def test_started_at_none_when_proc_missing(monkeypatch):
    def missing(self, encoding="utf-8"):
        raise FileNotFoundError(self)

    monkeypatch.setattr(Path, "read_text", missing)
    assert pi_budget.process_started_at(999_999) is None


def test_atom_never_kills():
    src = Path(pi_budget.__file__).read_text(encoding="utf-8")
    assert "os.kill" not in src
    assert "SIGKILL" not in src
    assert "SIGTERM" not in src
    assert ".kill(" not in src
    assert "Never kill" in src
