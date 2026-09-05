"""Stop a daemon cycle tree except registered detached issue-to-PR groups."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def process_tree() -> dict[int, list[int]]:
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,ppid="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {}
    mapping: dict[int, list[int]] = {}
    for line in (out.stdout or "").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            child, parent = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        mapping.setdefault(parent, []).append(child)
    return mapping


def children(pid: int, tree: dict[int, list[int]] | None = None) -> list[int]:
    mapping = process_tree() if tree is None else tree
    return list(mapping.get(pid) or [])


def walk(pid: int, tree: dict[int, list[int]] | None = None) -> list[int]:
    mapping = process_tree() if tree is None else tree
    found = [pid]
    for child in mapping.get(pid) or []:
        found.extend(walk(child, mapping))
    return found


def registered_worker_pgid(cycle: Path) -> set[int]:
    """Keep only live detached receipts. Nested Fala sessions are not workers."""
    kept: set[int] = set()
    if not cycle.is_dir():
        return kept
    for path in cycle.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            pid = int(row["pid"])
            if row.get("detached") is True and row.get("reaped") is not True:
                os.kill(pid, 0)
                kept.add(os.getpgid(pid))
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return kept


def cycle_targets(root_pid: int, cycle: Path) -> list[int]:
    """Return process-group ids that the watchdog may terminate."""
    keep_groups = registered_worker_pgid(cycle)
    groups: set[int] = set()
    for pid in walk(root_pid):
        try:
            pgid = os.getpgid(pid)
        except OSError:
            continue
        if pgid not in keep_groups:
            groups.add(pgid)
    return sorted(groups)


def signal_tree(pgids: list[int], signum: int) -> None:
    for pgid in reversed(pgids):
        try:
            os.killpg(pgid, signum)
        except OSError:
            try:
                os.kill(pgid, signum)
            except OSError:
                pass


def any_alive(pgids: list[int]) -> bool:
    for pgid in pgids:
        try:
            os.killpg(pgid, 0)
            return True
        except OSError:
            try:
                os.kill(pgid, 0)
                return True
            except OSError:
                continue
    return False


def stop(root_pid: int, cycle: Path, *, grace_seconds: float = 5.0) -> list[int]:
    targets = cycle_targets(root_pid, cycle)
    signal_tree(targets, signal.SIGTERM)
    deadline = time.monotonic() + max(0.0, float(grace_seconds))
    while time.monotonic() < deadline:
        if not any_alive(targets):
            return targets
        time.sleep(0.05)
    signal_tree(targets, signal.SIGKILL)
    return targets


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        return 2
    stop(int(args[0]), Path(args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
