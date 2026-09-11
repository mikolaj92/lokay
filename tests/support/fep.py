"""Helpers for standalone FEP/1 subprocess fixtures."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def request_from_adapter_manifest(manifest: Mapping[str, Any], *, run_id: str = "run") -> dict[str, Any]:
    """Turn Fala's adapter manifest into the FEP request used by Python fixtures."""
    request: dict[str, Any] = {
        "protocol": "fala-effector/1",
        "message_kind": "effector.request",
        "run_id": run_id,
        "process_id": str(manifest["process_id"]),
        "execution_id": str(manifest["execution_id"]),
        "attempt": int(manifest["attempt"]),
        "impulse_id": str(manifest.get("impulse_id") or "impulse:test"),
        "process_fingerprint": "process:test",
        "path_digest": "path:test",
        "capability": "lokay_atom",
        "input": dict(manifest.get("input") or {}),
        "config": dict(manifest.get("config") or {}),
        "output_contract_ref": "schema:test",
    }
    body = json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    request["message_id"] = "msg:sha256:" + hashlib.sha256(body.encode()).hexdigest()
    return request
