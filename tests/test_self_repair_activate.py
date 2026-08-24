"""Contracts for minimal exact self-repair activation atoms."""


def test_checkout_classifier_routes_planned_dirty_and_clean():
    from lokay.proc.classify_canonical_checkout import classify

    assert classify({"route": "planned"}, {})["reason"] == "planned"
    assert (
        classify({"route": "status"}, {"route": "classify", "dirty": True})["route"]
        == "dirty"
    )
    assert (
        classify({"route": "status"}, {"route": "classify", "dirty": False})["route"]
        == "clean"
    )


def test_head_classifier_accepts_exact_commit():
    from lokay.proc.classify_activated_head import classify

    out = classify(
        {"route": "status", "commit": "abc"},
        {"route": "clean"},
        {},
        {"route": "fetched"},
        {"route": "merged"},
        {"route": "classify", "head": "abc"},
    )
    assert out["route"] == "exact"


def test_head_classifier_requires_ancestry_for_later_head():
    from lokay.proc.classify_activated_head import classify

    out = classify(
        {"route": "status", "commit": "abc"},
        {"route": "clean"},
        {},
        {"route": "fetched"},
        {"route": "merged"},
        {"route": "classify", "head": "def"},
    )
    assert out["route"] == "ancestry"


def test_dirty_published_terminal_preserves_checkout():
    from lokay.proc.self_repair_activation_terminal import terminal

    out = terminal(
        {"commit": "abc", "path": "/x"},
        {"route": "dirty"},
        {"route": "published"},
        {},
        {},
        {},
        {},
        {},
        {},
    )["result"]
    assert (
        out["ok"] is True
        and out["activated"] is False
        and out["published"] is True
        and out["reason"] == "dirty_tree"
    )


def test_unpublished_dirty_terminal_fails_closed():
    from lokay.proc.self_repair_activation_terminal import terminal

    out = terminal(
        {"commit": "abc", "path": "/x"},
        {"route": "dirty"},
        {"route": "terminal", "reason": "dirty_tree"},
        {},
        {},
        {},
        {"route": "terminal", "reason": "dirty_tree"},
        {},
        {},
    )["result"]
    assert out["ok"] is False and out["reason"] == "dirty_tree"
