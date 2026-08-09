from lokay.gh_prs import _label_names


def test_label_names_preserves_valid_contract():
    assert _label_names([{"name": "ai:needs-review"}, {"name": "bug"}]) == ["ai:needs-review", "bug"]


def test_label_names_rejects_missing_or_malformed_contract():
    assert _label_names(None) is None
    assert _label_names({"name": "ai:needs-review"}) is None
    assert _label_names([{"name": 3}]) is None
