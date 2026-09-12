"""Helpers for standalone Fala 0.9 subprocess fixtures."""

from __future__ import annotations

from typing import Any, Mapping

from fala.protocol import Request, build_result, validate


def request_from_adapter_manifest(
    manifest: Mapping[str, Any], *, run_id: str = "run"
) -> Request:
    """Turn a leftover adapter-shaped mapping into a typed Fala 0.9 Request."""
    del run_id
    job = str(manifest.get("job") or manifest.get("process_id") or "")
    payload = dict(manifest.get("payload") or manifest.get("input") or {})
    config = dict(manifest.get("config") or {})
    return Request(
        sender="parent",
        recipient=job or "lokay-organ",
        job=job or "lokay-organ",
        payload=payload,
        config=config,
    )


def result_for(request: Request, payload: Mapping[str, Any]):
    """Typed result answering ``request``."""
    result = build_result(request, payload=payload)
    return validate(result, "result")
