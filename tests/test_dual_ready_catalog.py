"""Dual-ready catalog: wake cold repos that already have open ready labels."""

from lokay.proc.classify_dual_ready_repo import classify
from lokay.proc.dual_ready_catalog import SLOTS, run
from lokay.proc.reduce_dual_ready_catalog import apply_wake
from lokay.proc.select_dual_ready_repo import select


def test_select_probes_only_cold_repos():
    prepared = {
        "repos": ["a/hot", "a/cold"],
        "active_repos": ["a/hot"],
        "labels": ["work:ready", "ai:ready"],
    }
    assert select(prepared, slot=1)["route"] == "skip"
    assert select(prepared, slot=2) == {
        "ok": True,
        "route": "probe",
        "slot": 2,
        "repo": "a/cold",
        "labels": ["work:ready", "ai:ready"],
    }
    assert select(prepared, slot=3)["route"] == "empty"


def test_classify_wakes_only_dual_label_ready():
    selected = {
        "route": "probe",
        "repo": "mikolaj92/app-factory",
        "labels": ["work:ready", "ai:ready"],
    }
    assert classify(
        selected,
        {
            "route": "listed",
            "issues": [
                {"number": 64, "labels": ["work:ready", "ai:ready"]},
            ],
        },
    )["route"] == "wake"
    assert classify(
        selected,
        {"route": "listed", "issues": [{"number": 10, "labels": ["ai:needs-feedback"]}]},
    )["route"] == "empty"
    assert classify(selected, {"route": "failed", "error": "rate limit"})["route"] == (
        "failed"
    )


def test_catalog_fail_closed_when_prepare_failed():
    out = run(
        {"ok": False, "error": "dual-ready catalog exceeds authored slots"},
        config_path=None,
        live=True,
    )
    assert out["ok"] is False and "exceeds authored slots" in out["error"]


def test_catalog_overflow_is_fail_closed():
    out = run(
        {"ok": True, "repos": [f"o/r{i}" for i in range(SLOTS + 1)]},
        config_path=None,
        live=True,
    )
    assert out["ok"] is False and "exceeds authored slots" in out["error"]


def test_catalog_skip_does_not_list(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("skip must not list GitHub")

    monkeypatch.setattr("lokay.proc.list_dual_ready_issues.fetch", boom)
    out = run(
        {"ok": True, "route": "skip", "repos": ["o/r"], "active_repos": []},
        config_path=None,
        live=True,
    )
    assert out["skipped"] is True and out["wake_repos"] == []


def test_catalog_wakes_dual_ready_and_skips_empty(monkeypatch):
    def fake_fetch(selected, **_kwargs):
        repo = selected["repo"]
        issues = (
            [{"number": 64, "labels": ["work:ready", "ai:ready"]}]
            if repo == "mikolaj92/app-factory"
            else []
        )
        return {**selected, "ok": True, "route": "listed", "issues": issues}

    monkeypatch.setattr("lokay.proc.list_dual_ready_issues.fetch", fake_fetch)
    out = run(
        {
            "ok": True,
            "repos": ["mikolaj92/lokay", "mikolaj92/app-factory", "mikolaj92/product-1"],
            "active_repos": ["mikolaj92/lokay"],
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True
    assert out["wake_repos"] == ["mikolaj92/app-factory"]
    assert apply_wake(
        {"active_repos": ["mikolaj92/lokay"]}, out
    )["active_repos"] == ["mikolaj92/app-factory", "mikolaj92/lokay"]


def test_catalog_reuses_working_cache(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("cached wake must not list GitHub")

    monkeypatch.setattr("lokay.proc.list_dual_ready_issues.fetch", boom)
    out = run(
        {
            "ok": True,
            "repos": ["a/cold"],
            "active_repos": [],
        },
        config_path=None,
        live=True,
        working={"dual_ready_wake_repos": ["a/cold"]},
    )
    assert out == {"ok": True, "wake_repos": ["a/cold"], "cached": True}


def test_probe_failure_wakes_fail_closed(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.list_dual_ready_issues.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "failed",
            "error": "rate limit",
            "issues": [],
        },
    )
    out = run(
        {"ok": True, "repos": ["a/cold"], "active_repos": []},
        config_path=None,
        live=True,
    )
    assert out["wake_repos"] == ["a/cold"] and out["probe_failed"] is True
