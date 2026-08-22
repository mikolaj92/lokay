from __future__ import annotations



from lokay.mill_scope import (
    delivers,
    mill_repo,
    scoped_repos,
)




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










