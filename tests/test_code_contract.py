"""Code contract: one target, two blocks. In-memory host. No gh. No tasks."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.code import (
    CODE_BLOCKS,
    CodeContractError,
    CodeError,
    CodeTarget,
    MemoryCode,
    bind_code,
)


def _host(tmp_path: Path, ident: str = "desk/app") -> MemoryCode:
    return MemoryCode(CodeTarget(plugin="memory", id=ident), tmp_path)


def test_code_blocks_are_repo_and_pr_only() -> None:
    assert CODE_BLOCKS == ("repo", "pr")
    assert "task" not in CODE_BLOCKS
    assert "issue" not in CODE_BLOCKS


def test_memory_host_gives_branch_and_merges_pr(tmp_path: Path) -> None:
    host = _host(tmp_path)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    head = contract.repo.branch("topic")
    assert head == "topic"
    host.put_change(7, title="fix parser", head=head)
    merged = contract.pr.merge_commit(7)
    assert merged.state == "merged"
    assert merged.merge_method == "merge"
    assert merged.merge_method != "squash"
    assert contract.pr.list_open() == []
    assert contract.pr.get(7).head == "topic"


def test_memory_host_has_no_tasks(tmp_path: Path) -> None:
    host = _host(tmp_path)
    for name in (
        "list_issues",
        "get_issue",
        "list_tasks",
        "comment_issue",
        "mark_issue",
        "close_issue",
    ):
        assert not hasattr(host, name)
        assert not hasattr(host.repo, name)
        assert not hasattr(host.pr, name)
    assert not hasattr(host, "tasks")
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert not hasattr(contract, "tasks")
    assert not hasattr(contract, "issues")


def test_split_pr_and_repo_onto_two_targets_fails(tmp_path: Path) -> None:
    repo_host = _host(tmp_path / "bb", "bitbucket/app")
    pr_host = _host(tmp_path / "gh", "github/app")
    with pytest.raises(CodeContractError, match="two targets"):
        bind_code(repo_host.target, repo=repo_host.repo, pr=pr_host.pr)
    with pytest.raises(CodeContractError, match="two targets"):
        bind_code(pr_host.target, repo=repo_host.repo, pr=pr_host.pr)


def test_repo_block_path_clone_worktree(tmp_path: Path) -> None:
    host = _host(tmp_path)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert contract.repo.path() == tmp_path
    assert contract.repo.clone() == tmp_path
    assert tmp_path.is_dir()
    wt = contract.repo.worktree("ai/fix/1")
    assert wt.is_dir()
    assert wt != tmp_path
    assert wt.is_relative_to(tmp_path)


def test_pr_block_list_get_checks_comment_close(tmp_path: Path) -> None:
    host = _host(tmp_path)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    host.put_change(3, title="sieve", head="topic", checks_status="passed")
    rows = contract.pr.list_open()
    assert [row.number for row in rows] == [3]
    one = contract.pr.get(3)
    assert one.title == "sieve"
    assert one.target == host.target
    checks = contract.pr.checks(3)
    assert checks.status == "passed"
    assert checks.green is True
    noted = contract.pr.comment(3, "looks good")
    assert noted.comments == ("looks good",)
    closed = contract.pr.close(3)
    assert closed.state == "closed"
    assert closed.merge_method is None
    assert contract.pr.list_open() == []


def test_contract_modules_have_no_gh() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "lokay" / "code"
    banned = ("gh_prs", "gh_spec", "gh_json", "from lokay.gh", "import gh")
    files = [path for path in root.glob("*.py") if path.name != "github.py"]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} must not contain {token}"


def test_same_target_bind_keeps_one_place(tmp_path: Path) -> None:
    host = _host(tmp_path)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert contract.target == host.target
    assert contract.repo.target == contract.pr.target == contract.target
    assert contract.target.plugin == "memory"
    assert "/" in contract.target.id


def test_merge_commit_rejects_closed_change(tmp_path: Path) -> None:
    host = _host(tmp_path)
    host.put_change(1, title="x", head="h")
    host.pr.close(1)
    with pytest.raises(CodeError, match="cannot merge-commit"):
        host.pr.merge_commit(1)
