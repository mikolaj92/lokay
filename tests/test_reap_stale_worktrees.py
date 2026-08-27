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
        live_repos=set(),
        survey_failed=set(),
        covered={},
        heads={},
    )
    assert protection(**empty) == ""
    assert protection(**{**empty, "receipt_unknown": True}) == "receipt_state_unknown"
    assert protection(**{**empty, "live_repos": {"a/b"}}) == "live_issue_to_pr"
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


def test_overflow_skip_is_its_own_function():
    from lokay.proc.stale_worktree_catalog import SLOTS, overflow_skip

    assert overflow_skip([{"present": True}] * SLOTS) is None
    out = overflow_skip([{"present": True}] * (SLOTS + 1))
    assert out["ok"] is True and out["route"] == "skip"
    assert "leftover" not in out["reason"]


def test_skip_result_does_not_persist_or_park_labels():
    from lokay.proc.summarize_stale_worktree_reap import skip_result

    out = skip_result(
        pass_dir="/tmp/unused",
        collected={"ok": True, "receipt_safe": True, "deferred": []},
        catalog={"route": "skip", "skipped": True, "reason": "stale_worktree_overflow"},
        live=True,
    )
    assert out["ok"] is True and out["result"]["skipped"] is True
    assert "leftover" not in str(out["result"]["reason"])


def test_stale_worktree_catalog_overflow_skips_not_fail():
    from lokay.proc.stale_worktree_catalog import SLOTS, run

    out = run(
        {
            "ok": True,
            "candidates": [{"present": True} for _ in range(SLOTS + 1)],
        },
        config_path=None,
        live=True,
    )
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["skipped"] is True
    assert out["reason"] == "stale_worktree_overflow"
    assert out["count"] == SLOTS + 1
    assert out["effects"] == []


def test_stale_worktree_summarize_overflow_skip_does_not_block():
    from lokay.proc.summarize_stale_worktree_reap import summarize

    out = summarize(
        pass_dir="/tmp/unused",
        collected={"ok": True, "receipt_safe": True, "deferred": []},
        catalog={
            "ok": True,
            "route": "skip",
            "skipped": True,
            "reason": "stale_worktree_overflow",
            "count": 5,
            "slot_count": 4,
            "effects": [],
        },
        live=True,
    )
    assert out["ok"] is True
    assert out["result"]["skipped"] is True
    assert out["result"]["reason"] == "stale_worktree_overflow"
    assert out["result"]["reaped_count"] == 0


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
