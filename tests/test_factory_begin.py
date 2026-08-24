"""Contracts for minimal factory-begin atoms."""


def test_live_non_live_config_routes_terminal():
    from lokay.proc.classify_factory_mode import classify

    assert classify({"live": True, "mode": "dry-run"}) == {
        "ok": True,
        "route": "terminal",
        "reason": "mode_not_live",
    }


def test_scope_preserves_catalog_without_override(monkeypatch):
    from lokay.proc.select_factory_scope import select

    monkeypatch.delenv("LOKAY_MILL_REPO", raising=False)
    assert select({"repos": ["a/b", "c/d"]})["repos"] == ["a/b", "c/d"]


def test_terminal_classifier_prefers_preflight_failure():
    from lokay.proc.classify_factory_begin_terminal import classify

    assert classify({"route": "terminal"}, {}, {}, {})["kind"] == "preflight_failed"
