from lokay.gh_prs import _label_names, comment_bodies


def test_label_names_preserves_valid_contract():
    assert _label_names([{"name": "ai:needs-review"}, {"name": "bug"}]) == ["ai:needs-review", "bug"]


def test_label_names_rejects_missing_or_malformed_contract():
    assert _label_names(None) is None
    assert _label_names({"name": "ai:needs-review"}) is None
    assert _label_names([{"name": 3}]) is None


def test_comment_bodies_from_view():
    assert comment_bodies({"comments": [{"body": "a"}, "b", {"x": 1}]}) == ["a", "b"]
    assert comment_bodies({"comments": "nope"}) == []
    assert comment_bodies({}) == []
