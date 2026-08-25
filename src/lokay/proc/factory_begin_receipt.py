"""Keep factory_begin conduction a receipt, not the nested Fala cart."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_BEGIN_KEYS = (
    "ok",
    "pass_dir",
    "stuck_path",
    "planned",
    "live",
    "mode",
    "offline",
    "error",
    "health",
    "executed",
    "progress",
    "idle",
    "actions",
    "remaining",
    "issue_count",
)


def with_stuck(ledger: dict[str, Any]) -> dict[str, Any]:
    """Load the stuck ledger from disk when conduction carried only the path."""
    if "stuck" in ledger:
        return ledger
    from lokay.stuck import load_stuck

    return {**ledger, "stuck": load_stuck(Path(ledger["stuck_path"]))}


def harvest_receipt(out: dict[str, Any]) -> dict[str, Any]:
    """Authored harvest facts only — no nested fala/terminal/steps cart."""
    stuck = dict(out.get("stuck") or {})
    issues = stuck.get("issues") or {}
    receipt = {
        "ok": bool(out.get("ok")),
        "stuck_path": str(out.get("stuck_path") or ""),
        "stuck": stuck,
        "issue_count": len(issues) if isinstance(issues, dict) else 0,
    }
    error = out.get("error")
    if error:
        receipt["error"] = error
    return receipt


def begin_receipt(out: dict[str, Any]) -> dict[str, Any]:
    """Facts for factory_pass conduction. Listings stay on disk."""
    receipt = {key: out[key] for key in _BEGIN_KEYS if key in out}
    receipt.setdefault("ok", False)
    return receipt
