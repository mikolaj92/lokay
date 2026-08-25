"""First factory_pass atom: authored idle vs host. Never skip Fala from compose."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lokay.proc.survey_ttl import skip_idle_factory_pass


def classify(
    *,
    live: bool,
    stamp: Path | None = None,
    receipt: dict[str, Any] | None = None,
    now: float | None = None,
    probe: Callable[..., bool | None] | None = None,
) -> dict[str, Any]:
    """Return route=idle when the empty-survey TTL still holds; else host.

    Missing stamp, occupied last-pass, remaining work, probe failure, dry-run,
    or pytest on the operator mill always hosts. Fresh stamp does not refresh.
    """
    skipped = skip_idle_factory_pass(
        live=live, stamp=stamp, receipt=receipt, now=now, probe=probe
    )
    if skipped is None:
        return {"ok": True, "route": "host"}
    remaining = skipped.get("remaining") if isinstance(skipped, dict) else {}
    return {
        "ok": True,
        "route": "idle",
        "lane": "idle",
        "health": "idle",
        "idle": True,
        "live": bool(skipped.get("live", live)),
        "progress": int(skipped.get("progress") or 0),
        "remaining": remaining if isinstance(remaining, dict) else {},
        "reason": str(skipped.get("reason") or "recent_empty_survey"),
        "skipped": True,
    }
