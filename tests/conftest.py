"""Keep the host mill health capability out of this pytest process."""

from __future__ import annotations

import os

import pytest

_MILL_LEASE_KEYS = (
    "LOKAY_HEALTH_LEASE",
    "LOKAY_HEALTH_LEASE_PATH",
    "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
)


@pytest.fixture(autouse=True)
def _isolate_mill_health_lease() -> None:
    # Inherited mill lease makes factory_begin skip patched run_preflight
    # and fail-close against the host lock (health=preflight_failed).
    for key in _MILL_LEASE_KEYS:
        os.environ.pop(key, None)
    yield
    for key in _MILL_LEASE_KEYS:
        os.environ.pop(key, None)



@pytest.fixture(autouse=True)
def _isolate_live_issue_to_pr_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Occupancy must not scan the host mill's ~/.lokay/cycle during compose canaries."""
    monkeypatch.setattr(
        "lokay.proc.refresh_occupancy.live_issue_to_pr_receipts",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_worktrees.live_issue_to_pr_receipts",
        lambda *a, **k: [],
    )
