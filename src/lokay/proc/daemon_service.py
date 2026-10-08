"""One resident process conducts successive authored daemon graphs.

Fala owns each cycle. This module only decides whether the same process
asks for another graph, and how long it waits after a failed one.
"""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable, Mapping
from typing import Any

DEFAULT_GRAPH_PAUSE_SECONDS = 60.0
DEFAULT_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 300.0


def resolve_pause_seconds(
    explicit: float | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> float:
    """Pause between completed graphs. One LaunchAgent policy, not a tick."""
    if explicit is not None:
        try:
            value = float(explicit)
        except (TypeError, ValueError):
            value = DEFAULT_GRAPH_PAUSE_SECONDS
        return max(0.0, value)
    source = env if env is not None else os.environ
    raw = str(source.get("LOKAY_GRAPH_PAUSE_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_GRAPH_PAUSE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_GRAPH_PAUSE_SECONDS
    if value < 0.0:
        return DEFAULT_GRAPH_PAUSE_SECONDS
    return value


def next_pause(
    payload: Mapping[str, Any] | None,
    *,
    failures: int,
    pause_seconds: float,
) -> tuple[str, float, int]:
    """Return action, wait, and the failure count after this graph.

    A completed graph waits the steady pause. A failed graph waits a bounded
    exponential backoff and never starts the next graph immediately.
    """
    failed = not isinstance(payload, Mapping) or payload.get("ok") is not True
    if not failed:
        return "continue", max(0.0, float(pause_seconds)), 0
    count = max(1, int(failures) + 1)
    delay = min(MAX_BACKOFF_SECONDS, DEFAULT_BACKOFF_SECONDS * (2 ** (count - 1)))
    return "backoff", delay, count


class ServiceStop(BaseException):
    """SIGTERM or SIGINT asked this resident process to leave."""


def serve(
    run_graph: Callable[[], Mapping[str, Any]],
    *,
    pause_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    max_graphs: int | None = None,
    restart_needed: Callable[[], Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Conduct graphs until a signal, a host update, or max_graphs in a test.

    The stop signal ends the wait. It does not start another graph and it
    does not signal a graph that is already running. The caller still owns
    the singleton lock, so a replacement cannot overlap this process.

    ``restart_needed`` reports when the host checkout moved under this
    process (host-ff merged new main). The code imported here is stale then,
    so the process stops conducting graphs and returns ``host_updated`` for
    the caller to restart on the new code.
    """
    completed = 0
    failures = 0
    last: Mapping[str, Any] = {}
    moved: Mapping[str, Any] | None = None
    previous = signal.getsignal(signal.SIGTERM)
    previous_int = signal.getsignal(signal.SIGINT)
    stop = False

    def _request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    try:
        while max_graphs is None or completed < max_graphs:
            if stop:
                break
            moved = restart_needed() if restart_needed else None
            if moved:
                break
            last = run_graph()
            completed += 1
            if stop:
                break
            moved = restart_needed() if restart_needed else None
            if moved:
                break
            _action, delay, failures = next_pause(
                last, failures=failures, pause_seconds=pause_seconds
            )
            if max_graphs is not None and completed >= max_graphs:
                break
            try:
                if delay > 0.0:
                    sleep(delay)
            except ServiceStop:
                break
        if moved and not stop:
            return {
                "ok": True,
                "health": "host_updated",
                "reason": "host_updated",
                "restart_required": True,
                "graphs": completed,
                "head": moved.get("head"),
                "process_head": moved.get("process_head"),
                "last": dict(last),
            }
        return {
            "ok": True,
            "health": "stopped" if stop else "resident_complete",
            "graphs": completed,
            "reason": "stop_requested" if stop else "graph_budget",
            "last": dict(last),
        }
    finally:
        signal.signal(signal.SIGTERM, previous)
        signal.signal(signal.SIGINT, previous_int)
