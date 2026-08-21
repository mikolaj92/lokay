from __future__ import annotations

from pathlib import Path

from lokay.mill_scope import (
    DEFAULT_MILL_REPO,
    SKIP_REASON,
    delivers,
    mill_repo,
    scoped_repos,
)


def test_live_default_is_lokay(monkeypatch):
    monkeypatch.delenv("LOKAY_MILL_REPO", raising=False)
    assert mill_repo() == DEFAULT_MILL_REPO == "mikolaj92/lokay"
    assert delivers("mikolaj92/lokay") is True
    assert delivers("mikolaj92/Temida") is False
    assert delivers("") is False
    assert SKIP_REASON == "repo_not_delivered_by_mini_mill"


def test_env_overrides_mill_repo_for_hermetic_physics(monkeypatch):
    monkeypatch.setenv("LOKAY_MILL_REPO", "a/lib")
    assert mill_repo() == "a/lib"
    assert delivers("a/lib") is True
    assert delivers("mikolaj92/lokay") is False
    assert delivers("a/lib", mill="mikolaj92/lokay") is False


def test_mixed_catalog_clamps_to_mill_repo():
    deliver, skipped = scoped_repos(
        ["mikolaj92/Temida", "mikolaj92/lokay", "mikolaj92/takt"],
        mill="mikolaj92/lokay",
    )
    assert deliver == ["mikolaj92/lokay"]
    assert skipped == ["mikolaj92/Temida", "mikolaj92/takt"]


def test_test_catalog_without_mill_repo_is_delivered():
    deliver, skipped = scoped_repos(["a/busy", "a/clean"], mill="mikolaj92/lokay")
    assert deliver == ["a/busy", "a/clean"]
    assert skipped == []


def test_in_scope_uses_catalog_when_mill_is_absent():
    from lokay.mill_scope import in_scope

    catalog = ["a/busy", "a/clean"]
    assert in_scope("a/clean", catalog, mill="mikolaj92/lokay") is True
    assert in_scope("mikolaj92/Temida", catalog, mill="mikolaj92/lokay") is False


def test_in_scope_clamps_mixed_catalog():
    from lokay.mill_scope import in_scope

    catalog = ["mikolaj92/Temida", "mikolaj92/lokay"]
    assert in_scope("mikolaj92/lokay", catalog) is True
    assert in_scope("mikolaj92/Temida", catalog) is False


def test_empty_catalog_fails_closed_to_mill():
    from lokay.mill_scope import in_scope

    assert in_scope("mikolaj92/lokay", []) is True
    assert in_scope("mikolaj92/Temida", []) is False
    assert in_scope("mikolaj92/lokay", None) is True


def test_working_docs_name_this_host_mill_scope():
    """DoD is still merge-to-main; this host delivers lokay only."""
    root = Path(__file__).resolve().parents[1]
    working = (root / "docs" / "WORKING.md").read_text(encoding="utf-8")
    autonomy = (root / "docs" / "AUTONOMY.md").read_text(encoding="utf-8")
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    for text in (working, autonomy, graph):
        assert "mill_scope" in text
        assert "mikolaj92/lokay" in text
    assert "all work across\nconfigured repos (`repos.mikolaj92.yaml`)" not in working
    assert "mini mill" in working.lower()
    daemon = (root / "scripts" / "lokay-mill-daemon.sh").read_text(encoding="utf-8")
    assert "mill_scope=mikolaj92/lokay" in daemon
    assert "all managed source repos" not in daemon
