"""Atomic subprocess boundary: run the declared self-repair Fala subflow."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err
from lokay.self_repair import run_self_repair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-run-self-repair")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--incident-url", required=True)
    parser.add_argument("--evidence", default="")
    args = parser.parse_args(argv)
    result = run_self_repair(
        args.config,
        {
            "ok": False,
            "carrier_ok": True,
            "integrity_ok": False,
            "fingerprint": args.fingerprint,
            "incident_url": args.incident_url,
            "failure_evidence": args.evidence,
            "findings": [{"name": "confirmed_product_stall", "ok": False}],
        },
    )
    if result.get("ok"):
        return emit_exit({**result, "ok": True})
    return emit_exit(err("self-repair did not release gate", self_repair=result))


if __name__ == "__main__":
    raise SystemExit(main())
