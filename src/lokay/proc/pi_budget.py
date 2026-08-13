"""Atomic: observe whether a pid has run past a wall-clock budget. Never kill."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any, Callable

from lokay.envelope import emit_exit, err, ok

DEFAULT_BUDGET_S = 480
OVER_BUDGET_EXIT = 2


def process_started_at(pid: int) -> float | None:
    """Return start epoch seconds, or None if pid is not running. Never signals."""
    if pid <= 0:
        return None
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        uptime_raw = Path("/proc/uptime").read_text(encoding="utf-8")
    except OSError:
        return None
    rparen = raw.rfind(")")
    if rparen < 0:
        return None
    fields = raw[rparen + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        starttime_ticks = int(fields[19])
        uptime_s = float(uptime_raw.split()[0])
        clk_tck = os.sysconf("SC_CLK_TCK")
    except (ValueError, IndexError, OSError):
        return None
    if clk_tck <= 0:
        return None
    elapsed = uptime_s - (starttime_ticks / float(clk_tck))
    return time.time() - max(0.0, elapsed)


def check_pi_budget(
    pid: int,
    budget_s: int = DEFAULT_BUDGET_S,
    *,
    clock: Callable[[], float] | None = None,
    started_at: Callable[[int], float | None] | None = None,
) -> dict[str, Any]:
    """Observe pid vs budget. Does not send signals."""
    now_fn = clock or time.time
    start_fn = started_at or process_started_at
    start = start_fn(pid)
    if start is None:
        return ok(over_budget=False, pid=pid, elapsed_s=0, budget_s=budget_s)
    elapsed_s = max(0.0, now_fn() - start)
    return ok(
        over_budget=elapsed_s > float(budget_s),
        pid=pid,
        elapsed_s=elapsed_s,
        budget_s=budget_s,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay.proc.pi_budget")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET_S)
    args = parser.parse_args(argv)
    if args.pid <= 0:
        return emit_exit(err("pid must be a positive integer", pid=args.pid))
    if args.budget < 0:
        return emit_exit(err("budget must be >= 0", budget_s=args.budget))
    payload = check_pi_budget(args.pid, args.budget)
    if payload.get("over_budget"):
        return emit_exit(payload, code=OVER_BUDGET_EXIT)
    return emit_exit(payload, code=0)


if __name__ == "__main__":
    raise SystemExit(main())
