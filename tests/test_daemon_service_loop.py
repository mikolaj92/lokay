"""Resident daemon service loop: next graph, graceful stop, backoff, single-flight."""

from __future__ import annotations

import json
import os
import signal

import pytest

from lokay import preflight
from lokay.proc import daemon


@pytest.fixture
def restore_signals():
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.fixture
def boundaries(tmp_path, monkeypatch):
    """Patch OS/preflight boundaries; the singleton lock stays real (tmp)."""
    lock = tmp_path / "lokay.lock"
    monkeypatch.setattr(daemon, "_lokay_lock_path", lambda config_path: lock)
    monkeypatch.setattr(daemon, "prune_stale_health_leases", lambda directory: {})
    monkeypatch.setattr(
        daemon, "snapshot_process_head", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        daemon, "run_preflight", lambda *args, **kwargs: {"ok": True, "health": "current"}
    )
    monkeypatch.setattr(daemon, "revoke_health_lease", lambda: None)
    return lock


def _stub_subflow(monkeypatch, payloads, *, receipts_dir=None, on_graph=None):
    """Replace the daemon_entry graph with a recording fake."""
    calls: list[dict] = []

    def run(*, config_path, max_passes, preflight):
        index = len(calls)
        calls.append({"max_passes": max_passes, "preflight": preflight})
        payload = dict(payloads[index])
        receipt = payload.pop("receipt", None)
        if receipts_dir is not None and receipt is not None:
            receipts_dir.write_text(json.dumps(receipt), encoding="utf-8")
        if on_graph is not None:
            on_graph(index + 1)
        return payload

    monkeypatch.setattr("lokay.proc.daemon_entry_subflow.run", run)
    return calls


def _argv(tmp_path, *extra: str) -> list[str]:
    return [
        "--config",
        str(tmp_path / "config.yaml"),
        "--outbox",
        str(tmp_path / "outbox" / "incidents.log"),
        *extra,
    ]


def _envelopes(capsys) -> list[dict]:
    return [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    ]


def test_resident_daemon_schedules_next_graph_after_completion(
    tmp_path, monkeypatch, boundaries, restore_signals, capsys
):
    receipts = [
        {"health": "progress", "progress": 1, "ts": "2026-10-07T10:00:00+00:00"},
        {"health": "progress", "progress": 2, "ts": "2026-10-07T10:00:30+00:00"},
    ]
    payloads = [
        {"ok": True, "health": "progress", "receipt": receipts[0]},
        {"ok": True, "health": "progress", "receipt": receipts[1]},
    ]
    calls = _stub_subflow(
        monkeypatch,
        payloads,
        receipts_dir=boundaries.parent / "last-pass.json",
        on_graph=lambda done: (
            os.kill(os.getpid(), signal.SIGTERM) if done >= 2 else None
        ),
    )
    monkeypatch.setattr(daemon, "_sleep_until", lambda stop, seconds: None)

    rc = daemon.main(_argv(tmp_path, "--max-passes", "1", "--interval", "15"))

    assert rc == 0
    assert len(calls) == 2  # graph completion -> next graph, same process
    assert all(call["max_passes"] == 1 for call in calls)  # each graph bounded
    written = json.loads((boundaries.parent / "last-pass.json").read_text())
    assert written == receipts[1]  # two consecutive completed graph receipts
    lines = _envelopes(capsys)
    assert len(lines) == 2  # one observable envelope per graph
    assert all(line["ok"] for line in lines)


def test_term_drains_current_graph_and_exits_zero(
    tmp_path, monkeypatch, boundaries, restore_signals
):
    calls = _stub_subflow(
        monkeypatch,
        [{"ok": True, "health": "progress"}],
        on_graph=lambda done: os.kill(os.getpid(), signal.SIGTERM),
    )
    scheduled: list[float] = []
    monkeypatch.setattr(daemon, "_sleep_until", lambda stop, seconds: scheduled.append(seconds))

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 0
    assert len(calls) == 1  # drain, then stop: no next graph
    assert scheduled == []


def test_term_during_interval_wait_stops_without_next_graph(
    tmp_path, monkeypatch, boundaries, restore_signals
):
    calls = _stub_subflow(monkeypatch, [{"ok": True, "health": "progress"}])

    def wait_then_terminate(stop, seconds):
        stop["flag"] = True  # SIGTERM arrives during the schedule wait

    monkeypatch.setattr(daemon, "_sleep_until", wait_then_terminate)

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 0
    assert len(calls) == 1


def test_failed_graph_backs_off_and_is_observable(
    tmp_path, monkeypatch, boundaries, restore_signals, capsys
):
    payloads = [
        {"ok": False, "health": "survey_error", "code": "gate"},
        {"ok": False, "health": "survey_error", "code": "gate"},
        {"ok": True, "health": "progress"},
    ]
    calls = _stub_subflow(
        monkeypatch,
        payloads,
        on_graph=lambda done: (
            os.kill(os.getpid(), signal.SIGTERM) if done >= 3 else None
        ),
    )
    delays: list[float] = []
    monkeypatch.setattr(daemon, "_sleep_until", lambda stop, seconds: delays.append(seconds))

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 0  # transient failure never restarts the process
    assert len(calls) == 3
    assert delays == [15.0, 30.0]  # exponential, capped, never tight
    outbox = (tmp_path / "outbox" / "incidents.log").read_text().splitlines()
    assert len(outbox) == 2
    assert all(json.loads(line)["health"] == "survey_error" for line in outbox)


def test_backoff_resets_after_success(
    tmp_path, monkeypatch, boundaries, restore_signals
):
    payloads = [
        {"ok": False, "health": "gate"},
        {"ok": False, "health": "gate"},
        {"ok": True, "health": "progress"},
        {"ok": False, "health": "gate"},
    ]
    calls = _stub_subflow(
        monkeypatch,
        payloads,
        on_graph=lambda done: (
            os.kill(os.getpid(), signal.SIGTERM) if done >= 4 else None
        ),
    )
    delays: list[float] = []
    monkeypatch.setattr(daemon, "_sleep_until", lambda stop, seconds: delays.append(seconds))

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 0
    assert len(calls) == 4
    assert delays == [15.0, 30.0, 15.0]  # reset after the completed graph


def test_single_flight_lock_held_once_and_released(
    tmp_path, monkeypatch, boundaries, restore_signals
):
    calls = _stub_subflow(
        monkeypatch,
        [
            {"ok": True, "health": "progress"},
            {"ok": True, "health": "progress"},
        ],
        on_graph=lambda done: (
            os.kill(os.getpid(), signal.SIGTERM) if done >= 2 else None
        ),
    )
    acquires: list[str] = []
    real_acquire = preflight.acquire_run_lock

    def counting_acquire(path):
        acquires.append(str(path))
        return real_acquire(path)

    monkeypatch.setattr(daemon, "acquire_run_lock", counting_acquire)

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 0
    assert len(calls) == 2
    assert len(acquires) == 1  # one hold covers both graphs: no overlap
    assert str(boundaries) not in preflight._LOCKS
    assert preflight.acquire_run_lock(boundaries) is True  # re-acquirable
    preflight.release_run_lock(boundaries)


def test_overlap_second_instance_skips_without_graph(
    tmp_path, monkeypatch, boundaries, restore_signals, capsys
):
    calls = _stub_subflow(monkeypatch, [])
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda path: False)

    rc = daemon.main(_argv(tmp_path, "--interval", "15"))

    assert rc == 1
    assert calls == []  # no graph under a held singleton
    envelope = _envelopes(capsys)[0]
    assert envelope["health"] == "overlap"


def test_one_shot_mode_without_interval_is_unchanged(
    tmp_path, monkeypatch, boundaries, restore_signals, capsys
):
    calls = _stub_subflow(
        monkeypatch,
        [{"ok": True, "health": "progress"}],
    )

    rc = daemon.main(_argv(tmp_path))

    assert rc == 0
    assert len(calls) == 1
    assert _envelopes(capsys)[0]["ok"] is True
    assert str(boundaries) not in preflight._LOCKS
