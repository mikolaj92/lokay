"""The resident daemon conducts the next Fala graph in the same process."""

from __future__ import annotations

import signal

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from lokay.preflight import acquire_run_lock
from lokay.proc.daemon_service import next_pause, resolve_pause_seconds, serve


def test_completed_graph_waits_then_runs_the_next_one():
    calls = {"graphs": 0, "waits": []}

    def run_graph():
        calls["graphs"] += 1
        return {"ok": True, "health": "idle", "graphs_seen": calls["graphs"]}

    def sleep(seconds):
        calls["waits"].append(seconds)

    result = serve(run_graph, pause_seconds=60, sleep=sleep, max_graphs=2)

    assert result["graphs"] == 2
    assert result["health"] == "resident_complete"
    assert calls["waits"] == [60]
    assert result["last"]["graphs_seen"] == 2


def test_failed_graph_backs_off_and_does_not_overlap():
    running = {"depth": 0, "max_depth": 0}

    def run_graph():
        running["depth"] += 1
        running["max_depth"] = max(running["max_depth"], running["depth"])
        running["depth"] -= 1
        return {"ok": False, "health": "failed"}

    waits = []
    result = serve(
        run_graph,
        pause_seconds=60,
        sleep=waits.append,
        max_graphs=3,
    )

    assert running["max_depth"] == 1
    assert waits == [5, 10]
    assert result["graphs"] == 3


def test_stop_during_a_graph_lets_that_graph_finish():
    def run_graph():
        signal.raise_signal(signal.SIGTERM)
        return {"ok": True, "health": "progress", "finished": True}

    result = serve(
        run_graph, pause_seconds=60, sleep=lambda _seconds: None, max_graphs=None
    )

    assert result["graphs"] == 1
    assert result["last"]["finished"] is True
    assert result["health"] == "stopped"


def test_stop_during_pause_does_not_start_another_graph(monkeypatch):
    started = {"count": 0}

    def run_graph():
        started["count"] += 1
        return {"ok": True, "health": "progress"}

    def sleep(_seconds):
        signal.raise_signal(signal.SIGTERM)

    result = serve(run_graph, pause_seconds=60, sleep=sleep, max_graphs=None)

    assert started["count"] == 1
    assert result["health"] == "stopped"
    assert result["reason"] == "stop_requested"
    assert result["graphs"] == 1


def test_pause_comes_from_one_env_value():
    assert resolve_pause_seconds(env={}) == 60
    assert resolve_pause_seconds(env={"LOKAY_GRAPH_PAUSE_SECONDS": "15"}) == 15
    assert resolve_pause_seconds(explicit=0) == 0


def test_backoff_is_bounded():
    delay = next_pause({"ok": False}, failures=20, pause_seconds=60)[1]
    assert delay == 300


def test_resident_process_keeps_the_lock_until_it_exits(tmp_path: Path):
    script = tmp_path / "hold.py"
    script.write_text(
        textwrap.dedent(
            """
            import os
            import sys
            import time
            from pathlib import Path

            sys.path.insert(0, os.environ["SRC"])
            from lokay.preflight import acquire_run_lock

            lock = Path(sys.argv[1])
            assert acquire_run_lock(lock)
            Path(sys.argv[2]).write_text("held")
            time.sleep(30)
            """
        ),
        encoding="utf-8",
    )
    ready = tmp_path / "ready"
    child = subprocess.Popen(
        [sys.executable, str(script), str(tmp_path / "lokay.lock"), str(ready)],
        env={**os.environ, "SRC": str(Path(__file__).parents[1] / "src")},
    )
    try:
        for _ in range(50):
            if ready.is_file():
                break
            assert child.poll() is None
            import time

            time.sleep(0.05)
        assert ready.is_file()
        assert acquire_run_lock(tmp_path / "lokay.lock") is False
    finally:
        child.terminate()
        child.wait(timeout=5)
