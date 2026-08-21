import pytest

from lokay.safety import SafetyError, validate_argv


def test_blocks_force_push():
    with pytest.raises(SafetyError):
        validate_argv(["git", "push", "--force", "origin", "main"])


def test_blocks_force_with_lease():
    with pytest.raises(SafetyError):
        validate_argv(["git", "push", "--force-with-lease", "origin", "x"])


def test_blocks_repo_delete():
    with pytest.raises(SafetyError):
        validate_argv(["gh", "repo", "delete", "x/y"])


def test_allows_normal_push():
    validate_argv(["git", "push", "-u", "origin", "ai/fix/1-x"])


def test_allows_gh_pr_create():
    validate_argv(["gh", "pr", "create", "--title", "t", "--body", "b"])
