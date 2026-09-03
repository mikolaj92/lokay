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

# Nested factory_begin Fala keeps begin facts on these terminal atoms.
# Receipt must lift them; the parent never conducts the cart.
_NESTED_BEGIN_ATOMS = (
    "persist_factory_tick",
    "merge_leftover_remaining",
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


def _atom_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Prefer authored result envelope; else the flat atom values."""
    nested = item.get("result")
    if isinstance(nested, dict):
        return nested
    return item


def _nested_begin_facts(out: dict[str, Any]) -> dict[str, Any]:
    """Lift begin keys from persist_factory_tick / merge_leftover_remaining."""
    terminal = out.get("terminal")
    if not isinstance(terminal, dict):
        return {}
    facts: dict[str, Any] = {}
    for name in _NESTED_BEGIN_ATOMS:
        item = terminal.get(name)
        if not isinstance(item, dict):
            continue
        payload = _atom_payload(item)
        for key in _BEGIN_KEYS:
            if key in facts or key not in payload:
                continue
            facts[key] = payload[key]
    return facts


def begin_receipt(out: dict[str, Any]) -> dict[str, Any]:
    """Facts for factory_pass conduction. Listings stay on disk.

    Top-level begin keys win. When Fala left them only on nested terminal
    atoms (persist_factory_tick / merge_leftover_remaining), lift those.
    Nested fala / terminal / steps / stuck blob stay off the receipt.
    """
    receipt = {key: out[key] for key in _BEGIN_KEYS if key in out}
    nested = _nested_begin_facts(out)
    for key in _BEGIN_KEYS:
        if key not in receipt and key in nested:
            receipt[key] = nested[key]
    receipt.setdefault("ok", False)
    return receipt
