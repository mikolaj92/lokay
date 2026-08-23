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
