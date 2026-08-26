"""Lift record_pass so the path normalizer sees one authored tick."""

from __future__ import annotations

from typing import Any


def terminal(record_pass: dict[str, Any]) -> dict[str, Any]:
    payload = (
        record_pass.get("result")
        if isinstance(record_pass.get("result"), dict)
        else record_pass
    )
    if not isinstance(payload, dict) or not payload:
        payload = {"ok": False, "health": "record_pass_result_missing"}
    return {"ok": True, "result": payload}
