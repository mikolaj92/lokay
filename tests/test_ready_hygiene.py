"""Contracts for minimal authored ready-hygiene atoms."""

import os, time
from pathlib import Path
from types import SimpleNamespace
from lokay.proc import ready_hygiene


def test_classifies_only_orphan_ready():
    from lokay.proc.classify_ready_hygiene_issues import classify

    out = classify(
        {"route": "probe", "repo": "o/r"},
        {
            "route": "listed",
            "issues": [
                {"number": 1, "labels": ["ai:ready"]},
                {"number": 2, "labels": ["ai:ready", "work:ready"]},
            ],
        },
    )
    assert [x["number"] for x in out["candidates"]] == [1]


def test_candidate_overflow_fails_closed():
    from lokay.proc.reduce_ready_hygiene_candidates import reduce_candidates

    rows = [{"candidates": [{"number": i} for i in range(31)]}]
    assert reduce_candidates({}, rows, slot_count=30)["ok"] is False


def test_failed_probe_is_preserved():
    from lokay.proc.reduce_ready_hygiene_candidates import reduce_candidates

    out = reduce_candidates(
        {"route": "probe", "live": True},
        [{"repo": "o/r", "route": "failed"}],
        slot_count=30,
    )
    assert out["failed_repos"] == ["o/r"]


def test_planned_effect_is_not_counted_removed():
    from lokay.proc.reduce_ready_hygiene import reduce_state

    out = reduce_state(
        {"live": True},
        {"mutations_allowed": False, "failed_repos": []},
        [{"route": "planned", "repo": "o/r", "number": 1}],
    )
    assert (
        out["planned"] is True and out["applied"] is False and out["cleaned_count"] == 0
    )


def test_applied_effect_is_counted_removed():
    from lokay.proc.reduce_ready_hygiene import reduce_state

    out = reduce_state(
        {"live": True},
        {"mutations_allowed": True, "failed_repos": []},
        [{"route": "removed", "repo": "o/r", "number": 1}],
    )
    assert out["applied"] is True and out["cleaned_count"] == 1


def test_recent_stamp_helper_and_idle_ttl(tmp_path):
    stamp = tmp_path / "ready-hygiene.stamp"
    stamp.write_text("1")
    age = time.time() - 301
    os.utime(stamp, (age, age))
    assert (
        ready_hygiene.hygiene_recently_empty(stamp) is False
        and ready_hygiene.hygiene_recently_empty(
            stamp, ttl=ready_hygiene.IDLE_HYGIENE_TTL_SECONDS
        )
        is True
    )


def test_rate_limit_result_does_not_look_empty():
    from lokay.proc.reduce_ready_hygiene import reduce_state

    out = reduce_state(
        {"live": True}, {"mutations_allowed": True, "failed_repos": ["o/r"]}, []
    )
    assert out["probe_failed"] is True and out["applied"] is False


def test_catalog_skip_does_not_list():
    from lokay.proc.ready_hygiene_catalog import run

    out = run({"route": "skip", "repos": ["o/r"], "live": True}, config_path=None, live=True)
    assert out["skipped"] is True and out["cleaned_count"] == 0


def test_catalog_removes_one_orphan(monkeypatch):
    from lokay.proc import ready_hygiene_catalog

    monkeypatch.setattr(
        "lokay.proc.list_ready_hygiene_issues.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "listed",
            "issues": [{"repo": "o/r", "number": 1, "labels": ["ai:ready"]}],
        },
    )
    monkeypatch.setattr(
        "lokay.proc.remove_ready_hygiene_label.remove",
        lambda selected, **kwargs: {**selected, "ok": True, "route": "removed"},
    )
    out = ready_hygiene_catalog.run(
        {
            "ok": True,
            "route": "probe",
            "repos": ["o/r"],
            "ready_label": "ai:ready",
            "mutations_allowed": True,
            "live": True,
        },
        config_path=None,
        live=True,
    )
    assert out["cleaned_count"] == 1 and out["applied"] is True


def test_idle_leftover_ready_facade_is_gone():
    from lokay.compose import run

    assert not hasattr(ready_hygiene, "hygiene_idle_leftover_ready")
    assert not hasattr(run, "closeout_leftover_ready")
