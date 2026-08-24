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


def test_existing_delivery_closeout_is_explicit_fala_edge():
    from lokay.graph_run import describe_package

    path = next(p for p in describe_package()["paths"] if p["id"] == "issue_to_pr")
    by = {n["id"]: n for n in path["nodes"]}
    assert (
        by["close_existing_delivery"]["when"]["equals"] == "closeout"
        and by["issue_to_pr_subflow"]["when"]["equals"] == "deliver"
    )
