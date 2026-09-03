import json
from pathlib import Path
from lokay.proc.classify_stale_worktree_candidate import classify
from lokay.proc.keep_stale_worktree_candidate import apply as keep
from lokay.proc.resolve_existing_delivery import resolve


def test_collect_protection_is_its_own_function():
    from lokay.proc.collect_stale_worktree_candidates import protection

    empty = dict(
        repo="a/b",
        branch="ai/fix/1",
        issue=1,
        receipt_unknown=False,
        live_keys=set(),
        survey_failed=set(),
        covered={},
        heads={},
    )
    assert protection(**empty) == ""
    assert protection(**{**empty, "receipt_unknown": True}) == "receipt_state_unknown"
    assert protection(**{**empty, "live_keys": {("a/b", 1)}}) == "live_issue_to_pr"
    # Same repo, different issue is not KEEP (issue-scoped).
    assert protection(**{**empty, "live_keys": {("a/b", 99)}}) == ""
    assert protection(**{**empty, "survey_failed": {"a/b"}}) == "pr_survey_failed"
    assert (
        protection(**{**empty, "covered": {"a/b": {1}}}) == "covering_pr"
    )


def test_bound_slots_defers_overflow_without_failing():
    from lokay.proc.collect_stale_worktree_candidates import SLOTS, bound_slots

    rows = [
        {"repo": "a/b", "issue": i, "branch": f"ai/fix/{i}", "present": True}
        for i in range(1, SLOTS + 3)
    ]
    out = bound_slots(rows, pass_dir="/tmp/p", receipt_safe=True)
    assert out["ok"] is True
    assert len(out["candidates"]) == SLOTS
    assert len(out["deferred"]) == 2


def test_absent_candidate_is_explicit():
    assert classify({"present": False}, live=True)["route"] == "absent"


def test_protected_candidate_is_kept_without_git():
    out = classify(
        {"present": True, "repo": "a/b", "protected": "covering_pr"}, live=True
    )
    assert out["route"] == "keep" and out["row"]["reason"] == "covering_pr"


LEFTOVER_333 = {
    "paths": [
        "src/lokay/proc/factory_begin.py",
        "hot.py",
        "lokay/proc/factory_begin.py",
        "tests/test_hot_repos.py",
    ],
    "source": "agent",
    "worktree": (
        "/Users/mini-m4-main/.lokay/worktrees/mikolaj92__lokay/"
        "ai__fix__333-factory_begin-cold-survey-musi-pokry-sko-1ddbe4a4"
    ),
}


def _write_localize(root: Path, payload: dict) -> Path:
    loc = root / ".lokay"
    loc.mkdir(parents=True, exist_ok=True)
    path = loc / "localize.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def test_leftover_333_removes_even_when_live_and_dirty(tmp_path):
    """Foreign leftover sito beats live_issue_to_pr / dirty KEEP."""
    wt = _write_localize(tmp_path / "ai__fix__865-plugin", LEFTOVER_333)
    out = classify(
        {
            "present": True,
            "repo": "mikolaj92/lokay",
            "clone": str(tmp_path / "clone"),
            "path": str(wt),
            "branch": "ai/fix/865-plugin",
            "issue": 865,
            "protected": "live_issue_to_pr",
        },
        live=True,
    )
    assert out["route"] == "remove"
    assert out["row"]["reason"] == "foreign_localize"


def test_leftover_333_beats_unpublished_or_dirty_keep(tmp_path, monkeypatch):
    wt = _write_localize(tmp_path / "ai__fix__865-plugin", LEFTOVER_333)

    def boom(*_args, **_kwargs):
        raise AssertionError("leftover_status must not KEEP leftover sito")

    monkeypatch.setattr(
        "lokay.proc.classify_stale_worktree_candidate.leftover_status", boom
    )
    out = classify(
        {
            "present": True,
            "repo": "mikolaj92/lokay",
            "clone": str(tmp_path / "clone"),
            "path": str(wt),
            "branch": "ai/fix/865-plugin",
            "issue": 865,
            "protected": "",
        },
        live=True,
    )
    assert out["route"] == "remove"
    assert out["row"]["reason"] == "foreign_localize"


def test_this_issue_localize_still_keeps_live_protection(tmp_path):
    wt = _write_localize(
        tmp_path / "ai__fix__865-plugin",
        {
            "paths": ["src/lokay/localize.py"],
            "source": "deterministic",
            "issue": 865,
            "worktree": str(tmp_path / "ai__fix__865-plugin"),
        },
    )
    out = classify(
        {
            "present": True,
            "repo": "mikolaj92/lokay",
            "clone": str(tmp_path / "clone"),
            "path": str(wt),
            "branch": "ai/fix/865-plugin",
            "issue": 865,
            "protected": "live_issue_to_pr",
        },
        live=True,
    )
    assert out["route"] == "keep"
    assert out["row"]["reason"] == "live_issue_to_pr"


def test_unreadable_localize_does_not_force_remove(tmp_path):
    wt = tmp_path / "ai__fix__865-plugin"
    loc = wt / ".lokay"
    loc.mkdir(parents=True)
    (loc / "localize.json").write_text("{not-json", encoding="utf-8")
    out = classify(
        {
            "present": True,
            "repo": "mikolaj92/lokay",
            "path": str(wt),
            "issue": 865,
            "protected": "live_issue_to_pr",
        },
        live=True,
    )
    assert out["route"] == "keep"
    assert out["row"]["reason"] == "live_issue_to_pr"


def test_dry_run_candidate_is_kept():
    out = classify({"present": True, "repo": "a/b", "protected": ""}, live=False)
    assert out["route"] == "keep" and out["row"]["reason"] == "planned"


def test_keep_effect_is_physical_noop():
    out = keep(
        {"row": {"repo": "a/b", "path": "/tmp/x", "reason": "unpublished_or_dirty"}}
    )
    assert out["applied"] and out["row"]["kept"]


def test_existing_delivery_resolver_is_unrelated_to_reap():
    assert resolve({"route": "closed"}, {}, {})["route"] == "no_effect"


def test_stale_worktree_catalog_fail_closed_when_collect_failed():
    from lokay.proc.stale_worktree_catalog import run

    out = run(
        {"ok": False, "error": "stale worktree catalog exceeds authored slots"},
        config_path=None,
        live=True,
    )
    assert out["ok"] is False and "exceeds authored slots" in out["error"]


def test_overflow_bound_is_its_own_function():
    from lokay.proc.stale_worktree_catalog import SLOTS, overflow_bound

    assert len(overflow_bound([{"present": True}] * SLOTS)) == SLOTS
    out = overflow_bound([{"present": True, "issue": i} for i in range(SLOTS + 3)])
    assert len(out) == SLOTS
    assert out[0]["issue"] == 0


def test_stale_worktree_catalog_overflow_bounds_not_skip(monkeypatch):
    from lokay.proc import stale_worktree_catalog

    def classify(candidate, *, live):
        return {"ok": True, "route": "absent", "row": dict(candidate)}

    monkeypatch.setattr(
        "lokay.proc.classify_stale_worktree_candidate.classify", classify
    )
    out = stale_worktree_catalog.run(
        {
            "ok": True,
            "candidates": [{"present": True, "issue": i} for i in range(5)],
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True
    assert out.get("skipped") is not True
    assert out["bounded"] is True
    assert out["present_count"] == 5
    assert len(out["effects"]) == stale_worktree_catalog.SLOTS


def test_stale_worktree_summarize_persists_bounded_pass(tmp_path, monkeypatch):
    from lokay.proc.summarize_stale_worktree_reap import summarize

    monkeypatch.setattr(
        "lokay.proc.summarize_stale_worktree_reap._archive_gc",
        lambda **_k: {"ok": True, "pruned_count": 0},
    )
    monkeypatch.setattr(
        "lokay.proc.summarize_stale_worktree_reap.load_begin_working",
        lambda _p: ({}, {"actions": []}),
    )
    monkeypatch.setattr(
        "lokay.proc.summarize_stale_worktree_reap.save_begin_working",
        lambda *_a, **_k: None,
    )
    out = summarize(
        pass_dir=str(tmp_path),
        collected={"ok": True, "receipt_safe": True, "deferred": [{"present": True}]},
        catalog={
            "ok": True,
            "bounded": True,
            "effects": [
                {"ok": True, "row": {"kept": True, "reason": "planned"}},
            ],
        },
        live=False,
        config_path=None,
    )
    assert out["ok"] is True
    assert out["result"]["bounded"] is True
    assert out["result"]["reaped_count"] == 0
    assert out["result"]["archives"]["pruned_count"] == 0


def test_stale_worktree_catalog_keep_and_remove(monkeypatch):
    from lokay.proc import stale_worktree_catalog

    routes = ["keep", "remove", "absent", "absent"]

    def classify(candidate, *, live):
        slot = int(candidate.get("slot") or 0)
        return {"ok": True, "route": routes[slot - 1], "row": dict(candidate)}

    monkeypatch.setattr(
        "lokay.proc.classify_stale_worktree_candidate.classify", classify
    )
    monkeypatch.setattr(
        "lokay.proc.keep_stale_worktree_candidate.apply",
        lambda classified: {"ok": True, "applied": True, "row": {**classified["row"], "kept": True}},
    )
    monkeypatch.setattr(
        "lokay.proc.remove_stale_worktree_candidate.apply",
        lambda classified, **_k: {
            "ok": True,
            "applied": True,
            "row": {**classified["row"], "removed": True},
        },
    )
    collected = {
        "ok": True,
        "candidates": [
            {"present": True, "slot": 1},
            {"present": True, "slot": 2},
            {"present": False, "slot": 3},
            {"present": False, "slot": 4},
        ],
        "candidate_1": {"present": True, "slot": 1},
        "candidate_2": {"present": True, "slot": 2},
        "candidate_3": {"present": False, "slot": 3},
        "candidate_4": {"present": False, "slot": 4},
    }
    out = stale_worktree_catalog.run(collected, config_path=None, live=True)
    assert out["ok"] is True
    assert out["effects"][0]["row"]["kept"] is True
    assert out["effects"][1]["row"]["removed"] is True
    assert out["effects"][2]["route"] == "absent"


def test_remove_failed_rows_yield_oldest_slots_to_remainder(tmp_path):
    import os
    import time

    from lokay.proc.collect_stale_worktree_candidates import SLOTS, bound_slots
    from lokay.proc.remove_stale_worktree_candidate import defer_failed_removal

    now = time.time()
    rows = []
    for issue in range(1, SLOTS * 2 + 1):
        path = tmp_path / str(issue)
        path.mkdir()
        os.utime(path, (now - 100 + issue, now - 100 + issue))
        rows.append(
            {
                "repo": "a/b",
                "issue": issue,
                "branch": f"ai/fix/{issue}",
                "path": str(path),
                "present": True,
            }
        )

    first = bound_slots(rows, pass_dir=str(tmp_path), receipt_safe=True)
    assert [row["issue"] for row in first["candidates"]] == list(range(1, SLOTS + 1))
    for row in first["candidates"]:
        assert defer_failed_removal(Path(row["path"])) is True

    second = bound_slots(rows, pass_dir=str(tmp_path), receipt_safe=True)
    assert [row["issue"] for row in second["candidates"]] == list(
        range(SLOTS + 1, SLOTS * 2 + 1)
    )
