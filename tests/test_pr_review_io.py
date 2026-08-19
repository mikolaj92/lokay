from __future__ import annotations

import pytest

from lokay.config import Config, RepoConfig
from lokay import pr_review_io


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_review_worktree_skips_product_repos(tmp_path, repo: str) -> None:
    product_clone = tmp_path / repo.rsplit("/", 1)[-1]
    product_clone.mkdir()
    cfg = Config(repos=[RepoConfig(name=repo, clone_path=product_clone)])

    assert pr_review_io.review_worktree(cfg, repo) is None


def test_review_worktree_uses_lokay_clone(tmp_path) -> None:
    clone = tmp_path / "lokay"
    clone.mkdir()
    cfg = Config(
        repos=[RepoConfig(name=pr_review_io.MINI_MILL_REPO, clone_path=clone)]
    )

    assert pr_review_io.review_worktree(cfg, pr_review_io.MINI_MILL_REPO) == clone
