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
from lokay.runner import CommandResult, Runner


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


@pytest.mark.parametrize("case", [
    "clean", "evidence", "staged_evidence", "product", "conflict", "symlink",
    "staged_symlink", "parent_symlink", "branch", "status_unavailable", "unchanged",
])
def test_product_commit_to_repair_publication(implementation, tmp_path, monkeypatch, case):
    from lokay.organ.lanes import _clean_head
    from lokay.organ.publication import handle_publication
    from lokay.proc import pr_repair_receipts as receipts

    clone, tree, _, repo, branch, start = implementation
    # Admission and local attestation accept the producer's exact host evidence.
    assert admit(implementation, "preflight")["route"] == "ready"
    assert _clean_head(str(tree)) == start
    if case != "unchanged":
        (tree / "product.py").write_text("value = 43\n")
        assert commit_all(Runner(), tree, "repair", live=True)
    target = git(tree, "rev-parse", "HEAD").strip()
    if case == "clean":
        # A clean control uses a fresh checkout, never cleans the product worktree.
        clean_tree = tmp_path / "clean"
        git(tree, "clone", "-q", "--branch", branch, str(clone), str(clean_tree))
        tree = clean_tree
    elif case == "staged_evidence":
        git(tree, "add", ".lokay/approach.md", ".lokay/localize.json")
    elif case == "product":
        (tree / "product.py").write_text("uncommitted user work\n")
    elif case == "conflict":
        blob = git(tree, "rev-parse", "HEAD:.lokay/approach.md").strip()
        subprocess.run(
            ["git", "-C", str(tree), "update-index", "--index-info"],
            input="0 " + "0" * 40 + "\t.lokay/approach.md\n" + "".join(
                f"100644 {blob} {stage}\t.lokay/approach.md\n" for stage in (1, 2, 3)
            ), text=True, check=True,
        )
    elif case in {"symlink", "staged_symlink"}:
        plan = tree / ".lokay/approach.md"
        plan.unlink()
        plan.symlink_to("../product.py")
        if case == "staged_symlink":
            git(tree, "add", ".lokay/approach.md")
            plan.unlink()
            plan.write_text("regular working evidence\n")
    elif case == "parent_symlink":
        external = tmp_path / "evidence"
        (tree / ".lokay").rename(external)
        (tree / ".lokay").symlink_to(external, target_is_directory=True)

    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(tree, "remote", "set-url", "origin", str(remote))
    config = tmp_path / "config.yaml"
    state = tmp_path / "state"
    config.write_text(
        f"mode: live\nstate:\n  path: {state / 'state.jsonl'}\n"
        f"repos:\n  - name: {repo.name}\n    clone_path: {clone}\n"
    )
    pushes = []

    class LocalRunner(Runner):
        def run(self, spec, *, live):
            assert spec.argv[0] == "git", spec
            if "status" in spec.argv and case == "status_unavailable":
                return CommandResult(spec, True, 1, stderr="status unavailable")
            if "push" in spec.argv:
                # Read the real on-disk intent at the physical push boundary.
                pending = receipts.read(repo.name, 57, state_dir=state)["pending_push"]
                assert pending["push_attempted"] is True
                assert pending["start_head_sha"] == start
                assert pending["target_head_sha"] == target
                assert pending["repo"] == repo.name
                assert pending["branch"] == branch
                assert pending["pr"] == 57
                pushes.append(spec.argv)
            return super().run(spec, live=live)

    run = LocalRunner()
    monkeypatch.setattr("lokay.proc._common.runner", lambda *_a: run)
    monkeypatch.setattr("lokay.proc.push_branch.runner", lambda: run)
    monkeypatch.setattr("lokay.proc._common.mutations_allowed", lambda **_kw: True)
    monkeypatch.setattr("lokay.proc.push_branch.mutations_allowed", lambda **_kw: True)
    status = git(tree, "--no-optional-locks", "status", "--porcelain=v1", "-z")
    index_path = Path(git(tree, "rev-parse", "--absolute-git-dir").strip()) / "index"
    index = index_path.read_bytes()
    evidence = [(tree / path).read_bytes() for path in (".lokay/approach.md", ".lokay/localize.json")]
    inputs = {"live": True, "config_path": str(config), "head_sha": start, "repair_kind": "ci"}
    up = {
        "worktree_add": {"worktree": str(tree), "branch": branch if case != "branch" else "ai/fix/other"},
        "commit_initial_repair": {"committed": True},
        "test_local": {"ok": True, "passed": True},
        "assert_real_diff": {"ok": True, "real": True},
    }
    out = handle_publication("push", inputs, up, {
        "cfg": ["--config", str(config)], "live": ["--live"], "repo": repo.name,
        "issue_number": None, "pr_number": 57, "repair_mode": True, "branch": branch,
    })
    assert out is not None
    if case in {"clean", "evidence", "staged_evidence"}:
        assert out["ok"] is True, out
        assert len(pushes) == 1
        assert pushes[0] == ("git", "push", "-u", "origin", branch)
        assert git(remote, "rev-parse", f"refs/heads/{branch}").strip() == target
        assert out["head_sha"] == target
        pending = receipts.read(repo.name, 57, state_dir=state)["pending_push"]
        assert out["repair_push_intent_sha256"] == pending["intent_sha256"]
    else:
        assert out["ok"] is False, out
        assert out["reason"] == {
            "branch": "repair_push_local_branch_mismatch",
            "unchanged": "repair_push_no_new_sha",
        }.get(case, "repair_push_worktree_dirty")
        assert pushes == []
        assert not receipts.receipt_path(repo.name, 57, state_dir=state).exists()
        assert git(remote, "for-each-ref") == ""
    assert git(tree, "rev-parse", "HEAD").strip() == target
    assert git(tree, "branch", "--show-current").strip() == branch
    assert git(tree, "--no-optional-locks", "status", "--porcelain=v1", "-z") == status
    assert index_path.read_bytes() == index
    assert [(tree / path).read_bytes() for path in (".lokay/approach.md", ".lokay/localize.json")] == evidence


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
