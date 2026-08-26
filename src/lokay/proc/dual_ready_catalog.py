"""Probe the catalog for open dual-label ready (no 30-slot Fala unroll)."""

from __future__ import annotations

SLOTS = 30
DEFAULT_LABELS = ("work:ready", "ai:ready")


def _one_repo(
    prepared: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.classify_dual_ready_repo import classify
    from lokay.proc.list_dual_ready_issues import fetch
    from lokay.proc.record_dual_ready_repo import record
    from lokay.proc.select_dual_ready_repo import select

    selected = select(prepared, slot=slot)
    listed = {}
    if selected.get("route") == "probe":
        listed = fetch(selected, config_path=config_path, live=live)
    return record(selected, classify(selected, listed))


def run(
    prepared: dict,
    *,
    config_path: str | None,
    live: bool,
    working: dict | None = None,
) -> dict:
    from lokay.proc.reduce_dual_ready_catalog import reduce_state

    if not prepared.get("ok", True):
        return dict(prepared)
    cached = dict(working or {}).get("dual_ready_wake_repos")
    if isinstance(cached, list):
        return {
            "ok": True,
            "wake_repos": sorted({str(name) for name in cached if str(name)}),
            "cached": True,
        }
    if prepared.get("recent_empty") or prepared.get("route") == "skip":
        return {"ok": True, "wake_repos": [], "skipped": True}
    repos = list(prepared.get("repos") or [])
    if len(repos) > SLOTS:
        return {
            "ok": False,
            "error": "dual-ready catalog exceeds authored slots",
            "count": len(repos),
            "slot_count": SLOTS,
        }
    scoped = {**prepared, "labels": list(prepared.get("labels") or list(DEFAULT_LABELS))}
    rows = [
        _one_repo(scoped, slot=slot, config_path=config_path, live=live)
        for slot in range(1, len(repos) + 1)
    ]
    return reduce_state(scoped, rows)
