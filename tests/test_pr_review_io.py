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


class _EvidenceRunner:
    def run_checked(self, spec, *, live):
        from lokay.runner import CommandResult
        import json

        return CommandResult(
            spec=spec,
            executed=live,
            returncode=0,
            stdout=json.dumps({"number": 12, "title": "change", "comments": []}),
        )

    def run(self, spec, *, live):
        from lokay.runner import CommandResult

        if spec.argv[1:3] == ("pr", "diff"):
            return CommandResult(
                spec=spec, executed=live, returncode=1, stderr="GitHub unavailable"
            )
        return CommandResult(spec=spec, executed=live, returncode=0, stdout="checks")


def test_pr_review_diff_failure_is_not_review_evidence() -> None:
    with pytest.raises(RuntimeError, match="GitHub unavailable"):
        pr_review_io.load_pr_evidence(
            _EvidenceRunner(), "mikolaj92/lokay", 12, live=True
        )


def test_pr_review_source_pins_diff_failure_semantics() -> None:
    from pathlib import Path

    source = Path(pr_review_io.__file__).read_text(encoding="utf-8")
    assert "PR review refuses to substitute a GitHub error for the code diff." in source
