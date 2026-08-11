"""Atomic: create or reuse one confirmed-stall incident in canonical Lokay."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.preflight import report_recovery_incident


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-incident")
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--evidence", default="")
    args = parser.parse_args(argv)
    incident_url = report_recovery_incident(
        fingerprint=args.fingerprint,
        evidence=args.evidence,
    )
    if not incident_url:
        return emit_exit(err("deduplicated recovery incident unavailable"))
    return emit_exit(
        ok(
            fingerprint=args.fingerprint,
            failure_evidence=args.evidence,
            incident_url=incident_url,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
