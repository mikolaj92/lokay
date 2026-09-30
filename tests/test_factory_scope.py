from __future__ import annotations

from lokay.factory_scope import (
    delivers,
    factory_repo,
    scoped_repos,
)


def test_env_overrides_factory_repo_for_hermetic_physics(monkeypatch):
    monkeypatch.setenv("LOKAY_REPO_SCOPE", "a/lib")
    assert factory_repo() == "a/lib"
    assert delivers("a/lib") is True
    assert delivers("mikolaj92/lokay") is False
    assert delivers("a/lib", lokay="mikolaj92/lokay") is False


def test_mixed_catalog_clamps_to_factory_repo():
    deliver, skipped = scoped_repos(
        ["mikolaj92/Temida", "mikolaj92/lokay", "mikolaj92/takt"],
        lokay="mikolaj92/lokay",
    )
    assert deliver == ["mikolaj92/lokay"]
    assert skipped == ["mikolaj92/Temida", "mikolaj92/takt"]


def test_empty_scope_is_the_full_catalog(monkeypatch):
    monkeypatch.delenv("LOKAY_REPO_SCOPE", raising=False)
    assert factory_repo() == ""
    catalog = ["mikolaj92/Temida", "mikolaj92/lokay", "mikolaj92/takt"]
    deliver, skipped = scoped_repos(catalog)
    assert deliver == catalog
    assert skipped == []
    assert delivers("mikolaj92/Temida", catalog=catalog) is True
    assert delivers("mikolaj92/lokay", catalog=catalog) is True
