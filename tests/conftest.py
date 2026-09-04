"""Keep the host lokay health capability out of this pytest process."""

from __future__ import annotations

import os

import pytest

_LOKAY_LEASE_KEYS = (
    "LOKAY_HEALTH_LEASE",
    "LOKAY_HEALTH_LEASE_PATH",
    "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
)


@pytest.fixture(autouse=True)
def _isolate_lokay_health_lease() -> None:
    # Inherited lokay lease makes factory_begin skip patched run_preflight
    # and fail-close against the host lock (health=preflight_failed).
    for key in _LOKAY_LEASE_KEYS:
        os.environ.pop(key, None)
    yield
    for key in _LOKAY_LEASE_KEYS:
        os.environ.pop(key, None)



@pytest.fixture(autouse=True)
def _isolate_live_issue_to_pr_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Occupancy must not scan the host lokay's ~/.lokay/cycle during compose canaries."""
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_worktrees.live_issue_to_pr_receipts",
        lambda *a, **k: [],
    )


@pytest.fixture(autouse=True)
def _isolate_fala_runtime_environment() -> None:
    """Fala discovery and native loading must not leak between tests."""
    keys = ("FALA_HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH")
    before = {key: os.environ.get(key) for key in keys}
    yield
    for key, value in before.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
