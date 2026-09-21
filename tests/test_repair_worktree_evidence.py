"""Real implementation output must be admissible at both exact-SHA repair gates."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lokay.config import Config, RepoConfig
from lokay.git_commit import commit_all
from lokay.git_worktree import _repair_worktree_identity, ensure_repair_worktree, worktree_dir
from lokay.proc.worktree_add import verify_repair_start_identity
from lokay.runner import Runner


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True)


@pytest.fixture
def implementation(tmp_path, monkeypatch):
    # All Git effects stay in this test's temporary clone; no network/push needed.
    clone = tmp_path / "clone"
    clone.mkdir()
    git(clone, "init", "-q", "-b", "main")
    git(clone, "config", "user.name", "Repair Test")
    git(clone, "config", "user.email", "repair@example.test")
    (clone / ".lokay").mkdir()
    (clone / ".lokay/approach.md").write_text("old issue plan\n")
    (clone / ".lokay/localize.json").write_text(json.dumps({"paths": ["product.py"]}))
    (clone / "product.py").write_text("value = 1\n")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "base with tracked evidence")
    git(clone, "remote", "add", "origin", str(clone))
    cfg = Config(worktrees_root=tmp_path / "worktrees")
    repo = RepoConfig(name="o/r", clone_path=clone)
    branch = "ai/fix/42-task"
    tree = worktree_dir(cfg, repo, branch)
    tree.parent.mkdir(parents=True)
    git(clone, "worktree", "add", "-qb", branch, str(tree))
    (tree / ".lokay/approach.md").write_text("issue 42 plan\n")
    (tree / ".lokay/localize.json").write_text(json.dumps({"paths": ["product.py"], "issue": 42}))
    (tree / "product.py").write_text("value = 42\n")
    assert commit_all(Runner(), tree, "implementation", live=True)
    sha = git(tree, "rev-parse", "HEAD").strip()
    assert git(tree, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == ["product.py"]
    assert set(git(tree, "diff", "--name-only").splitlines()) == {".lokay/approach.md", ".lokay/localize.json"}
    monkeypatch.setattr("lokay.gh_prs.gh_json", lambda *_a, **_kw: {
        "headRefOid": sha, "headRepository": {"nameWithOwner": "o/r"},
    })
    return clone, tree, cfg, repo, branch, sha


def admit(implementation, gate):
    clone, tree, cfg, repo, branch, sha = implementation
    if gate == "ensure":
        assert ensure_repair_worktree(Runner(), cfg, repo, branch, sha, head_repo=repo.name, live=True) == tree
        return {"route": "ready"}
    return verify_repair_start_identity(Runner(), repo=repo.name, pr=57, worktree=tree, expected_head_sha=sha)


@pytest.mark.parametrize("gate", ["ensure", "preflight"])
@pytest.mark.parametrize("staged", [False, True])
def test_implementation_commit_evidence_enters_exact_sha_repair(implementation, gate, staged):
    clone, tree, _, _, branch, sha = implementation
    if staged:
        git(tree, "add", ".lokay/approach.md", ".lokay/localize.json")
    before = git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    index = (Path(git(tree, "rev-parse", "--absolute-git-dir").strip()) / "index").read_bytes()
    evidence = [(tree / path).read_bytes() for path in (".lokay/approach.md", ".lokay/localize.json")]
    result = admit(implementation, gate)
    assert result["route"] == "ready", result
    if gate == "preflight":
        assert result["worktree_dirt"] == "evidence"
    assert git(tree, "rev-parse", "HEAD").strip() == sha
    assert git(tree, "branch", "--show-current").strip() == branch
    assert Path(git(tree, "rev-parse", "--git-common-dir").strip()).resolve() == (clone / ".git").resolve()
    assert git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all") == before
    assert (Path(git(tree, "rev-parse", "--absolute-git-dir").strip()) / "index").read_bytes() == index
    assert [(tree / path).read_bytes() for path in (".lokay/approach.md", ".lokay/localize.json")] == evidence
    # A repair can now produce a new product SHA without committing host evidence.
    (tree / "product.py").write_text("value = 43\n")
    assert commit_all(Runner(), tree, "repair", live=True)
    assert git(tree, "rev-parse", "HEAD").strip() != sha
    assert git(tree, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == ["product.py"]
    assert [(tree / path).read_bytes() for path in (".lokay/approach.md", ".lokay/localize.json")] == evidence


@pytest.mark.parametrize("gate", ["ensure", "preflight"])
@pytest.mark.parametrize("dirt", [
    "product", "staged_product", "untracked_product", "other_lokay", "quoted_path",
    "rename_into_evidence", "rename_out_of_evidence", "symlink", "staged_symlink", "parent_symlink",
])
def test_product_dirt_is_not_evidence_and_is_preserved(implementation, gate, dirt):
    _, tree, _, _, _, sha = implementation
    plan = tree / ".lokay/approach.md"
    if dirt in {"product", "staged_product"}:
        (tree / "product.py").write_text("user change\n")
        if dirt == "staged_product":
            git(tree, "add", "product.py")
    elif dirt in {"untracked_product", "other_lokay", "quoted_path"}:
        name = {"untracked_product": "new.py", "other_lokay": ".lokay/product.py", "quoted_path": 'odd\nname -> approach.md'}[dirt]
        (tree / name).write_text("user change\n")
    elif dirt == "rename_into_evidence":
        plan.unlink()
        git(tree, "mv", "product.py", ".lokay/approach.md")
    elif dirt == "rename_out_of_evidence":
        git(tree, "mv", ".lokay/approach.md", "user-plan.md")
    elif dirt in {"symlink", "staged_symlink"}:
        plan.unlink()
        plan.symlink_to("../product.py")
        if dirt == "staged_symlink":
            git(tree, "add", ".lokay/approach.md")
            # The index remains a symlink even though the working file is regular.
            plan.unlink()
            plan.write_text("regular working evidence\n")
    else:
        external = tree.parent / "external-evidence"
        (tree / ".lokay").rename(external)
        (tree / ".lokay").symlink_to(external, target_is_directory=True)
    before = git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    diff = git(tree, "diff", "HEAD", "--binary")
    if gate == "ensure":
        with pytest.raises(RuntimeError, match="repair worktree has product dirt"):
            admit(implementation, gate)
    else:
        result = admit(implementation, gate)
        assert result["route"] == "missing"
        assert result["reason"] == "repair_start_product_dirt"
    assert git(tree, "rev-parse", "HEAD").strip() == sha
    assert git(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all") == before
    assert git(tree, "diff", "HEAD", "--binary") == diff


@pytest.mark.parametrize("identity", ["sha", "branch", "repository"])
def test_evidence_allowance_does_not_weaken_identity(implementation, tmp_path, identity):
    clone, tree, _, _, branch, sha = implementation
    if identity == "sha":
        sha = "f" * 40
    elif identity == "branch":
        branch = "ai/fix/other"
    else:
        clone = tmp_path / "unrelated"
        clone.mkdir()
        git(clone, "init", "-q")
    with pytest.raises(RuntimeError):
        _repair_worktree_identity(Runner(), clone, tree, branch, sha)
