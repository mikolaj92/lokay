"""First block: open or reuse the stall incident. Does not push to main."""

from __future__ import annotations

from lokay.envelope import ok


def run(*, config_path: str | None) -> dict:
    from lokay.preflight import report_recovery_incident

    url = report_recovery_incident(
        fingerprint="did_not_move",
        evidence="last pass did not move",
        config_path=config_path,
    )
    if not url:
        return ok(route="skip", reason="incident_unavailable", department="self_repair")
    return ok(
        route="run",
        department="self_repair",
        fingerprint="did_not_move",
        incident_url=url,
        evidence="last pass did not move",
    )
