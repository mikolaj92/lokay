from __future__ import annotations

import json
import sys
from typing import Any


def ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def err(message: str, **fields: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **fields}


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def emit_exit(payload: dict[str, Any], code: int | None = None) -> int:
    emit(payload)
    if code is not None:
        return code
    return 0 if payload.get("ok", False) else 1


def read_stdin_json() -> dict[str, Any] | list[Any] | None:
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    return json.loads(raw)
