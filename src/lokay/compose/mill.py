"""Composer: run factory_pass until true idle or budget exhausted.

Continuous miller for the factory: keep calling compose_factory_pass (parent
Fala) until idle, stall, or max_passes. Does not sleep/poll forever — one fire
runs a bounded pass budget (external schedulers re-invoke mill).
"""

from __future__ import annotations

import argparse
import os
import secrets
from typing import Any

from lokay.envelope import emit_exit
from lokay.preflight import health_lease_status, revoke_health_lease, run_preflight
from lokay.proc._common import add_config_live, load_cfg


def compose_mill(
    *,
    config_path: str | None,
    live: bool,
    max_passes: int = 8,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the mill under one process-tree health capability."""
    inherited_lease = os.environ.get("LOKAY_HEALTH_LEASE", "")
    owns_lease = False
    owns_lease_path = False
    required_empty = []
    for key in ("LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH"):
        if key not in os.environ:
            os.environ[key] = ""
            required_empty.append(key)
    if (
        preflight is None
        and live
        and not inherited_lease
        and not os.environ.get("LOKAY_HEALTH_LEASE_PATH")
    ):
        cfg = load_cfg(argparse.Namespace(config=config_path))
        os.environ["LOKAY_HEALTH_LEASE_PATH"] = str(
            cfg.state_path.parent / f"health-lease-{os.getpid()}-{secrets.token_hex(8)}"
        )
        owns_lease_path = True
    try:
        if preflight is None and live:
            # A direct lokay-mill invocation owns preflight and must delegate its
            # result through the parent Fala subprocess. Otherwise factory_begin
            # repeats preflight and reports this process's lock as contention.
            preflight = run_preflight(config_path, remediate=True, issue_lease=True)
            owns_lease = not inherited_lease and bool(
                os.environ.get("LOKAY_HEALTH_LEASE")
            )
            if preflight.get("ok") and owns_lease:
                lease_ok, lease_reason = health_lease_status()
                if not lease_ok:
                    preflight = {
                        **preflight,
                        "ok": False,
                        "lease": False,
                        "lease_reason": lease_reason,
                    }
        return _compose_mill(
            config_path=config_path,
            live=live,
            max_passes=max_passes,
            preflight=preflight,
        )
    finally:
        if owns_lease:
            revoke_health_lease()
        if owns_lease_path:
            os.environ.pop("LOKAY_HEALTH_LEASE_PATH", None)
        for key in required_empty:
            os.environ.pop(key, None)


def _compose_mill(
    *,
    config_path: str | None,
    live: bool,
    max_passes: int = 8,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if preflight is None:
        preflight = run_preflight(config_path, remediate=True) if live else {"ok": True}
    from lokay.proc.product_entry_subflow import run

    return run(
        config_path=config_path,
        live=live,
        max_passes=max_passes,
        preflight=preflight,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-mill")
    add_config_live(p)
    p.add_argument(
        "--max-passes",
        type=int,
        default=8,
        help="stop after N tick passes even if not idle (default 8)",
    )
    args = p.parse_args(argv)
    return emit_exit(
        compose_mill(
            config_path=args.config,
            live=bool(args.live),
            max_passes=int(args.max_passes),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
