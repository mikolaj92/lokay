from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.compose.mill import compose_mill
from lokay.envelope import emit_exit, err
from lokay.preflight import acquire_run_lock, revoke_health_lease, run_preflight
from lokay.self_repair import run_self_repair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-daemon")
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--outbox", required=True)
    args = parser.parse_args(argv)
    lock = Path.home() / ".lokay" / "mill.lock"
    if not acquire_run_lock(lock):
        payload = err("preflight failed; overlapping run", health="preflight_failed", code="overlap")
    else:
        try:
            health = run_preflight(args.config, remediate=True)
            if health.get("ok"):
                payload = compose_mill(config_path=args.config, live=True, max_passes=args.max_passes)
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
    if not payload.get("ok"):
        try:
            outbox = Path(args.outbox); outbox.parent.mkdir(parents=True, exist_ok=True)
            with outbox.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"health": payload.get("health"), "code": payload.get("code", "gate")}) + "\n")
        except OSError:
            pass
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
