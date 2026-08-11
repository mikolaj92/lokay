from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from lokay.compose.mill import compose_mill
from lokay.envelope import emit_exit, err
from lokay.config import load_config
from lokay.preflight import (
    acquire_run_lock,
    report_recovery_incident,
    revoke_health_lease,
    run_preflight,
)
from lokay.recovery_history import history_path_for, observe_run, record_observation
from lokay.self_repair import run_self_repair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-daemon")
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--outbox", required=True)
    args = parser.parse_args(argv)
    lock = Path.home() / ".lokay" / "mill.lock"
    os.environ["LOKAY_HEALTH_LEASE_PATH"] = str(
        lock.parent / f"health-lease-{os.getpid()}-{secrets.token_hex(8)}"
    )
    if not acquire_run_lock(lock):
        payload = err("mill skipped; overlapping run", health="overlap", code="overlap")
    else:
        try:
            health = run_preflight(args.config, remediate=True, issue_lease=True)
            if health.get("ok"):
                cfg = load_config(args.config)
                try:
                    state_offset = cfg.state_path.stat().st_size
                except OSError:
                    state_offset = 0
                payload = compose_mill(
                    config_path=args.config,
                    live=True,
                    max_passes=args.max_passes,
                    preflight=health,
                )
                observation = observe_run(
                    state_path=cfg.state_path,
                    state_offset=state_offset,
                    mill=payload,
                )
                confirmed = record_observation(
                    history_path_for(cfg.state_path), observation
                )
                if confirmed is not None:
                    incident_url = report_recovery_incident(
                        fingerprint=str(confirmed["fingerprint"]),
                        evidence=str(confirmed.get("evidence") or ""),
                    )
                    recovery_health = {
                        "ok": False,
                        "carrier_ok": True,
                        "integrity_ok": False,
                        "fingerprint": str(confirmed["fingerprint"]),
                        "incident_url": incident_url,
                        "failure_evidence": str(confirmed.get("evidence") or ""),
                        "findings": [
                            {"name": "confirmed_product_stall", "ok": False}
                        ],
                    }
                    repair = run_self_repair(args.config, recovery_health)
                    if repair.get("ok"):
                        payload = err(
                            "confirmed stall repaired; restart required before product work",
                            health="self_repair_restart_required",
                            confirmed_stall=confirmed,
                            self_repair=repair,
                        )
                    else:
                        payload = err(
                            "confirmed stall; dedicated self-repair did not release gate",
                            health="self_repair_failed",
                            confirmed_stall=confirmed,
                            self_repair=repair,
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
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
