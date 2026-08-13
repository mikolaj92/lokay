"""Atomic: capture the state-log boundary before one product mill run."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_live, load_cfg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-begin")
    add_config_live(parser)
    args = parser.parse_args(argv)
    cfg = load_cfg(args)
    state_path = cfg.state_path
    try:
        offset = state_path.stat().st_size
    except OSError:
        offset = 0
    reconciled = {"ok": True, "closed": 0}
    try:
        from lokay.preflight import reconcile_incident_ledger

        reconciled = reconcile_incident_ledger(cfg)
    except Exception:  # noqa: BLE001
        pass
    return emit_exit(
        ok(
            state_path=str(state_path),
            state_offset=offset,
            incidents_closed=int(reconciled.get("closed") or 0),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
