"""Second block: run the existing self_repair child. Only after the incident."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.self_repair import run_self_repair


def run(incident: Mapping[str, Any], *, config_path: str | None) -> dict:
    if str(incident.get("route") or "") != "run":
        return ok(
            route="skip",
            department="self_repair",
            reason=str(incident.get("reason") or "not_selected"),
        )
    result = run_self_repair(
        config_path,
        {
            "ok": False,
            "carrier_ok": True,
            "integrity_ok": False,
            "fingerprint": str(incident.get("fingerprint") or "did_not_move"),
            "incident_url": str(incident.get("incident_url") or ""),
            "failure_evidence": str(incident.get("evidence") or ""),
            "findings": [{"name": "confirmed_product_stall", "ok": False}],
        },
    )
    return {**result, "department": "self_repair"}
