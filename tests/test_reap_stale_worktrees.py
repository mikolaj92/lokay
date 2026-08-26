from pathlib import Path
from lokay.proc.classify_stale_worktree_candidate import classify
from lokay.proc.keep_stale_worktree_candidate import apply as keep
from lokay.proc.resolve_existing_delivery import resolve


def test_absent_candidate_is_explicit():
    assert classify({"present": False}, live=True)["route"] == "absent"


def test_protected_candidate_is_kept_without_git():
    out = classify(
        {"present": True, "repo": "a/b", "protected": "covering_pr"}, live=True
    )
    assert out["route"] == "keep" and out["row"]["reason"] == "covering_pr"


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
