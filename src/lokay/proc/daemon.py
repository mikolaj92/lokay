from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from lokay.compose.daemon_cycle import compose_daemon_cycle
from lokay.config import load_config
from lokay.envelope import emit_exit, err, process_exit_code
from lokay.git_host_ff import snapshot_process_head
from lokay.pass_receipt import read_pass_receipt
from lokay.preflight import acquire_run_lock, revoke_health_lease, run_preflight
from lokay.self_repair import run_self_repair


def _mill_lock_path(config_path: str) -> Path:
    """Same OS advisory lock as preflight: beside configured state.path."""
    try:
        cfg = load_config(config_path)
        return (cfg.state_path.parent / "mill.lock").expanduser().absolute()
    except (OSError, ValueError, FileNotFoundError):
        # Overlap short-circuit before a readable config still needs a lock path.
        return (Path.home() / ".lokay" / "mill.lock").expanduser().absolute()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-daemon")
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--outbox", required=True)
    args = parser.parse_args(argv)
    lock = _mill_lock_path(args.config)
    os.environ["LOKAY_HEALTH_LEASE_PATH"] = str(
        lock.parent / f"health-lease-{os.getpid()}-{secrets.token_hex(8)}"
    )
    if not acquire_run_lock(lock):
        payload = err("mill skipped; overlapping run", health="overlap", code="overlap")
    else:
        try:
            root = os.environ.get("LOKAY_ROOT", "").strip()
            if root:
                snapshot_process_head(Path(root))
            health = run_preflight(args.config, remediate=True, issue_lease=True)
            if health.get("ok"):
                payload = compose_daemon_cycle(
                    config_path=args.config,
                    max_passes=args.max_passes,
                )
            elif health.get("operational_overlap"):
                payload = err(
                    "preflight skipped; overlapping run",
                    health="overlap",
                    code="overlap",
                    preflight=health,
                )
            elif not health.get("carrier_ok"):
                payload = err("carrier preflight failed; self-repair and product work blocked", health="carrier_failed", preflight=health)
            else:
                repair = run_self_repair(args.config, health)
                if repair.get("ok"):
                    payload = err(
                        "self-repair validated; restart required before product work",
                        health="self_repair_restart_required", self_repair=repair,
                    )
                else:
                    payload = err(
                        "preflight failed; dedicated self-repair did not release gate",
                        health="self_repair_failed", preflight=health, self_repair=repair,
                    )
        finally:
            revoke_health_lease()
    # A held singleton is an expected launchd overlap, not a preflight
    # incident. Report it to the caller but do not feed it into the failure
    # outbox where it can be mistaken for source health needing repair.
    if not payload.get("ok") and payload.get("health") != "overlap":
        try:
            outbox = Path(args.outbox); outbox.parent.mkdir(parents=True, exist_ok=True)
            with outbox.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"health": payload.get("health"), "code": payload.get("code", "gate")}) + "\n")
        except OSError:
            pass
    last_pass = None
    try:
        last_pass = read_pass_receipt(path=lock.parent / "last-pass.json")
    except OSError:
        last_pass = None
    return emit_exit(payload, code=process_exit_code(payload, last_pass=last_pass))


if __name__ == "__main__":
    raise SystemExit(main())
