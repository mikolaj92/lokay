from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import time
from pathlib import Path

from lokay.config import load_config
from lokay.envelope import emit, emit_exit, err, process_exit_code
from lokay.git_host_ff import snapshot_process_head
from lokay.pass_receipt import read_pass_receipt
from lokay.preflight import (
    acquire_run_lock,
    prune_stale_health_leases,
    release_run_lock,
    revoke_health_lease,
    run_preflight,
)

_MIN_INTERVAL_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 900.0


def _lokay_lock_path(config_path: str) -> Path:
    """Same OS advisory lock as preflight: beside configured state.path."""
    try:
        cfg = load_config(config_path)
        return (cfg.state_path.parent / "lokay.lock").expanduser().absolute()
    except (OSError, ValueError, FileNotFoundError):
        # Overlap short-circuit before a readable config still needs a lock path.
        return (Path.home() / ".lokay" / "lokay.lock").expanduser().absolute()


def _failure_outbox(outbox: str, payload: dict) -> None:
    # A held singleton is an expected launchd overlap, not a preflight
    # incident. Report real gate/graph failures to the caller but do not feed
    # overlaps into the failure outbox where they can be mistaken for source
    # health needing repair.
    if payload.get("ok") or payload.get("health") == "overlap":
        return
    try:
        outbox_path = Path(outbox)
        outbox_path.parent.mkdir(parents=True, exist_ok=True)
        with outbox_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "health": payload.get("health"),
                        "code": payload.get("code", "gate"),
                    }
                )
                + "\n"
            )
    except OSError:
        pass


def _conduct_once(args: argparse.Namespace, lock: Path) -> dict:
    """Conduct one bounded daemon-entry graph with a fresh health lease.

    The Fala daemon_entry graph owns the complete work cycle: preflight and
    recovery gates, the pass ceiling, and the receipt. This returns when the
    graph ends; it never starts a second graph.
    """
    os.environ["LOKAY_HEALTH_LEASE_PATH"] = str(
        lock.parent / f"health-lease-{os.getpid()}-{secrets.token_hex(8)}"
    )
    try:
        root = os.environ.get("LOKAY_ROOT", "").strip()
        if root:
            snapshot_process_head(Path(root), refresh=True)
        health = run_preflight(args.config, remediate=True, issue_lease=True)
        if not health.get("ok"):
            return health
        from lokay.proc.daemon_entry_subflow import run

        return run(
            config_path=args.config,
            max_passes=args.max_passes,
            preflight=health,
        )
    finally:
        revoke_health_lease()


def _sleep_until(stop: dict[str, bool], seconds: float) -> None:
    """Interruptible wait: the shutdown handler flips stop within one step."""
    deadline = time.monotonic() + max(0.0, seconds)
    while not stop["flag"]:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return
        time.sleep(min(0.2, remaining))


def _serve(args: argparse.Namespace, lock: Path) -> int:
    """Resident service: conduct repeated bounded Fala graphs in this process.

    The daemon_entry graph owns each complete work cycle; this loop only
    schedules the next one. The singleton lock is held for the process
    lifetime, so graphs stay strictly sequential (single-flight). A failed
    graph backs off exponentially and is observable via stdout and the
    failure outbox; it never restarts the process. SIGTERM/SIGINT stop the
    schedule, drain the current bounded graph, release the lock, and exit 0.
    """
    stop = {"flag": False}

    def request_shutdown(_signum: int, _frame: object) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    interval = max(_MIN_INTERVAL_SECONDS, float(args.interval))
    failures = 0
    try:
        while not stop["flag"]:
            try:
                payload = _conduct_once(args, lock)
            except Exception as exc:
                # Observable transient failure; the service stays resident.
                payload = err(
                    str(exc) or type(exc).__name__,
                    health="daemon_loop",
                    code="daemon_loop",
                )
            emit(payload)
            _failure_outbox(args.outbox, payload)
            if stop["flag"]:
                break
            if payload.get("ok"):
                failures = 0
                delay = interval
            else:
                failures += 1
                delay = min(interval * 2 ** min(failures - 1, 10), _MAX_BACKOFF_SECONDS)
            _sleep_until(stop, delay)
    finally:
        release_run_lock(lock)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-daemon")
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--outbox", required=True)
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="seconds between graphs; resident service when set, one bounded graph when omitted",
    )
    args = parser.parse_args(argv)
    lock = _lokay_lock_path(args.config)
    prune_stale_health_leases(lock.parent)
    if not acquire_run_lock(lock):
        payload = err("lokay skipped; overlapping run", health="overlap", code="overlap")
    elif args.interval is None:
        payload = _conduct_once(args, lock)
    else:
        return _serve(args, lock)
    _failure_outbox(args.outbox, payload)
    last_pass = None
    try:
        last_pass = read_pass_receipt(path=lock.parent / "last-pass.json")
    except OSError:
        last_pass = None
    release_run_lock(lock)
    return emit_exit(payload, code=process_exit_code(payload, last_pass=last_pass))


if __name__ == "__main__":
    raise SystemExit(main())
