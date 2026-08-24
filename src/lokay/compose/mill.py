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

from lokay.compose.factory import compose_factory_pass
from lokay.envelope import emit_exit, err, ok
from lokay.passkit.health import evaluate_mill_stop
from lokay.proc._common import add_config_live, load_cfg
from lokay.proc.closeout import run_closeout_leftover
from lokay.preflight import health_lease_status, revoke_health_lease, run_preflight


def closeout_leftover_ready(*, config_path: str | None, live: bool) -> dict[str, Any]:
    return run_closeout_leftover(config_path=config_path, live=live)


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


def _compose_mill(
    *,
    config_path: str | None,
    live: bool,
    max_passes: int = 8,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if preflight is None:
        preflight = run_preflight(config_path, remediate=True) if live else {"ok": True}
    if not preflight.get("ok"):
        return err(
            "preflight failed; product workflow blocked",
            health="preflight_failed",
            preflight=preflight,
            live=live,
            idle=False,
            progress=0,
            results=[],
        )
    from lokay.proc.product_pass_budget_subflow import run

    return run(config_path=config_path, live=live, max_passes=max_passes)


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
