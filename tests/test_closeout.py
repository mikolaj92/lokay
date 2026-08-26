"""Closeout and authored leftover-closeout atom contracts."""

from pathlib import Path
from types import SimpleNamespace
from lokay.proc import closeout


def test_open_issue_with_merged_fixes_pr_removes_ready_labels(monkeypatch):
    monkeypatch.setattr(
        closeout, "load_cfg", lambda _: SimpleNamespace(config_path=None)
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_: True)
    monkeypatch.setattr(closeout, "runner", lambda _: object())
    monkeypatch.setattr(
        closeout, "find_pr_fixing_issue", lambda *_a, **_k: {"number": 41}
    )
    monkeypatch.setattr(
        closeout, "_park_ready", lambda **_k: {"ok": True, "removed": True}
    )
    out = closeout.run_closeout(repo="o/r", issue=7, config_path=None, live=True)
    assert out["delivered"] and out["labels_removed"] and out["pr"] == 41


def test_recent_stamp_is_a_mechanical_fact(tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1")
    assert closeout.leftover_recently_empty(stamp)


def test_label_candidates_deduplicate_by_repo_issue():
    from lokay.proc.reduce_leftover_candidates import reduce_candidates

    prepared = {"route": "probe", "live": True, "mutations_allowed": True}
    rows = [
        {"candidates": [{"repo": "o/r", "number": 7}]},
        {"candidates": [{"repo": "o/r", "number": 7}]},
    ]
    out = reduce_candidates(prepared, rows, slot_count=30)
    assert out["candidates"] == [{"repo": "o/r", "number": 7}]


def test_candidate_overflow_fails_closed():
    from lokay.proc.reduce_leftover_candidates import reduce_candidates

    rows = [{"candidates": [{"repo": "o/r", "number": i} for i in range(31)]}]
    assert reduce_candidates({"route": "probe"}, rows, slot_count=30)["ok"] is False


def test_rate_limit_probe_remains_failed():
    from lokay.proc.classify_leftover_probe import classify

    out = classify(
        {"route": "probe", "repo": "o/r", "label": "ai:ready"},
        {"route": "failed", "error": "API rate limit exceeded"},
    )
    assert out["ok"] and out["route"] == "failed" and out["candidates"] == []


def test_failed_probe_is_not_empty_and_does_not_apply():
    from lokay.proc.reduce_leftover_closeout import reduce_state

    out = reduce_state(
        {"route": "probe", "live": True},
        {"failed_repos": ["o/r"], "mutations_allowed": True},
        [],
    )
    assert out["probe_failed"] and not out["applied"] and out["closed_out"] == []


def test_dry_run_candidate_is_planned_not_removed():
    from lokay.proc.reduce_leftover_closeout import reduce_state

    out = reduce_state(
        {"route": "probe", "live": False},
        {"failed_repos": [], "mutations_allowed": False},
        [{"route": "planned", "repo": "o/r", "number": 7}],
    )
    assert (
        out["planned"]
        and not out["labels_removed"]
        and out["closed_out"] == [{"repo": "o/r", "issue": 7, "planned": True}]
    )


def test_leftover_closeout_subflow_uses_handful_of_ticks():
    import inspect
    from lokay.proc.leftover_closeout_subflow import run

    source = inspect.getsource(run)
    assert "max_ticks=16" in source
    assert "max_ticks=768" not in source


def test_leftover_catalog_fail_closed_when_prepare_failed():
    from lokay.proc.leftover_catalog import run

    out = run(
        {"ok": False, "error": "leftover closeout catalog exceeds authored slots"},
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and out["skipped"] is True
    assert out["route"] == "skip" and "exceeds authored slots" in out["error"]
    assert out["probe_failed"] is False


def test_leftover_catalog_overflow_is_fail_closed():
    from lokay.proc.leftover_catalog import REPO_SLOTS, run

    out = run(
        {"ok": True, "route": "probe", "repos": [f"o/r{i}" for i in range(REPO_SLOTS + 1)]},
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and out["skipped"] is True
    assert out["route"] == "skip" and "exceeds authored slots" in out["error"]
    assert out["probe_failed"] is False


def test_leftover_catalog_stops_after_first_probe_fail(monkeypatch):
    from lokay.proc.leftover_catalog import run

    calls = []

    def fetch(selected, **kwargs):
        calls.append(selected.get("repo"))
        return {"ok": True, "route": "failed", "error": "rate limit", "numbers": []}

    monkeypatch.setattr("lokay.proc.list_leftover_closed_ready.fetch", fetch)
    out = run(
        {
            "ok": True,
            "route": "probe",
            "repos": [f"o/r{i}" for i in range(8)],
            "labels": ["work:ready"],
            "live": True,
            "mutations_allowed": True,
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and out["skipped"] is True
    assert out["reason"] == "leftover_probe_failed"
    assert out["probe_failed"] is True
    assert calls == ["o/r0"]


def test_leftover_catalog_skip_does_not_list(monkeypatch):
    from lokay.proc.leftover_catalog import run

    def boom(*_a, **_k):
        raise AssertionError("skip must not list GitHub")

    monkeypatch.setattr("lokay.proc.list_leftover_closed_ready.fetch", boom)
    out = run(
        {"ok": True, "route": "skip", "repos": ["o/r"], "live": True, "mutations_allowed": False},
        config_path=None,
        live=True,
    )
    assert out["skipped"] is True and out["leftover_closed"] == 0


def test_leftover_catalog_parks_one_candidate(monkeypatch):
    from lokay.proc import leftover_catalog

    monkeypatch.setattr(
        "lokay.proc.list_leftover_closed_ready.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "listed",
            "numbers": [7],
        },
    )
    monkeypatch.setattr(
        "lokay.proc.park_leftover_candidate.park",
        lambda selected, **kwargs: {**selected, "ok": True, "route": "removed"},
    )
    out = leftover_catalog.run(
        {
            "ok": True,
            "route": "probe",
            "repos": ["o/r"],
            "labels": ["work:ready", "ai:ready"],
            "mutations_allowed": True,
            "live": True,
        },
        config_path=None,
        live=True,
    )
    assert out["leftover_closed"] == 1 and out["applied"] is True


def test_leftover_catalog_park_failure_fails_closed(monkeypatch):
    from lokay.proc.leftover_catalog import run

    monkeypatch.setattr(
        "lokay.proc.list_leftover_closed_ready.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "listed",
            "numbers": [7],
        },
    )
    monkeypatch.setattr(
        "lokay.proc.park_leftover_candidate.park",
        lambda selected, **kwargs: {"ok": False, "error": "leftover park failed"},
    )
    out = run(
        {
            "ok": True,
            "route": "probe",
            "repos": ["o/r"],
            "labels": ["work:ready"],
            "mutations_allowed": True,
            "live": True,
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and out["skipped"] is True
    assert out["route"] == "skip" and out["error"] == "leftover park failed"


def test_leftover_catalog_candidate_overflow_fails_closed(monkeypatch):
    from lokay.proc.leftover_catalog import CANDIDATE_SLOTS, run

    monkeypatch.setattr(
        "lokay.proc.list_leftover_closed_ready.fetch",
        lambda selected, **kwargs: {
            **selected,
            "ok": True,
            "route": "listed",
            "numbers": list(range(1, CANDIDATE_SLOTS + 2)),
        },
    )
    out = run(
        {
            "ok": True,
            "route": "probe",
            "repos": ["o/r"],
            "labels": ["work:ready"],
            "mutations_allowed": True,
            "live": True,
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and out["skipped"] is True
    assert out["route"] == "skip" and "exceed authored slots" in out["error"]
    assert out["probe_failed"] is False
    assert out["reason"] == "candidates_exceed_slots"


def test_existing_delivery_closeout_is_explicit_fala_edge():
    from lokay.graph_run import describe_package

    path = next(p for p in describe_package()["paths"] if p["id"] == "issue_to_pr")
    by = {n["id"]: n for n in path["nodes"]}
    assert (
        by["close_existing_delivery"]["when"]["equals"] == "closeout"
        and by["issue_to_pr_subflow"]["when"]["equals"] == "deliver"
    )
