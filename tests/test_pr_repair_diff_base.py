"""Repair scope applies to unpublished repair, not the original PR."""

import pytest

from lokay.organ.publication import handle_publication


@pytest.mark.parametrize("repair_mode,expected", [(True, "@{upstream}"), (False, "origin/main")])
def test_publication_diff_base_matches_delivery_mode(monkeypatch, repair_mode, expected):
    from lokay.proc import assert_real_diff_subflow

    observed = {}

    def run(**kwargs):
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(assert_real_diff_subflow, "run", run)
    ctx = dict(cfg=None, live=True, repo="a/b", issue_number=None,
               pr_number=85 if repair_mode else None, repair_mode=repair_mode,
               branch="ai/fix/79")
    result = handle_publication("assert_real_diff", {},
                              {"worktree_add": {"worktree": "/tmp/repair"}}, ctx)
    assert result == {"ok": True}
    assert observed.get("base", "origin/main") == expected
