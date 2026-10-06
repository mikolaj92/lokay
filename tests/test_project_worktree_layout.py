import subprocess
from pathlib import Path

import pytest

from lokay.config import Config, RepoConfig, load_config
from lokay.git_worktree import iter_worktrees, project_worktree_root, worktree_dir


def test_clone_siblings_places_coding_checkout_next_to_main(tmp_path):
    repo = RepoConfig(name="owner/project", clone_path=tmp_path / "Developer/project/main")
    cfg = Config(worktrees_layout="clone-siblings", worktrees_root=tmp_path / "unused")
    assert worktree_dir(cfg, repo, "ai/fix/42-title") == tmp_path / "Developer/project/ai__fix__42-title"


def test_load_layout_and_project_override_without_resolving_symlinks(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    config = tmp_path / "config.yaml"
    config.write_text(f"worktrees:\n  layout: clone-siblings\n  project_roots:\n    owner/project: {link}\n")
    cfg = load_config(config)
    assert cfg.worktrees_layout == "clone-siblings"
    repo = RepoConfig(name="owner/project", clone_path=tmp_path / "main")
    assert project_worktree_root(cfg, repo) == link


@pytest.mark.parametrize("layout", ["siblings", "", None, 4])
def test_invalid_layout_rejected(layout):
    with pytest.raises(ValueError, match="worktrees.layout"):
        Config(worktrees_layout=layout)


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout


def make_clone(path):
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "base")
    return path


def test_sibling_iterator_only_returns_canonical_managed_registry_entries(tmp_path):
    root = tmp_path / "project"
    clone = make_clone(root / "main")
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", worktrees_root=tmp_path / "unused")
    managed = root / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    git(clone, "worktree", "add", "-b", "human", str(root / "human"))
    git(clone, "worktree", "add", "-b", "ai/fix/43-other", str(root / "wrong-name"))
    git(clone, "worktree", "add", "--detach", str(root / "self-repair__abc"))
    foreign = make_clone(tmp_path / "foreign")
    git(foreign, "worktree", "add", "-b", "ai/fix/44-foreign", str(root / "ai__fix__44-foreign"))
    (root / "ai__fix__45-plain").mkdir()
    (root / ".ai__fix__46.lokay-preserved").mkdir()
    (root / "ai__fix__47-link").symlink_to(managed, target_is_directory=True)
    assert iter_worktrees(cfg, repo) == [(managed, "ai/fix/42-title")]
    assert git(clone, "branch", "--show-current").strip() == "main"


def test_live_receipt_uses_loaded_catalog_and_project_root(tmp_path, monkeypatch):
    from lokay.proc.issue_delivery_occupancy import _worktree_paths_for_live_receipt
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    config = tmp_path / "config.yaml"
    config.write_text(f"worktrees:\n  layout: clone-siblings\nrepos:\n  - name: owner/project\n    clone_path: {clone}\n")
    monkeypatch.setenv("LOKAY_CONFIG", str(config))
    assert _worktree_paths_for_live_receipt("owner/project", 42) == [managed]


@pytest.mark.parametrize("starting", [False, True])
def test_unknown_catalog_lookup_keeps_receipt_occupied(tmp_path, monkeypatch, starting):
    import json
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
    config = tmp_path / "config.yaml"
    config.write_text("repos: []\n")
    monkeypatch.setenv("LOKAY_CONFIG", str(config))
    receipt = {"repo": "owner/unknown", "issue": 42, "pid": 999, "launch_id": "test"}
    if starting:
        receipt["starting"] = True
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    (cycle / "receipt.json").write_text(json.dumps(receipt))
    assert live_issue_to_pr_receipts(cycle, pid_alive=lambda _: True, issue_closed=lambda *_: False) == [receipt]


def test_self_repair_resolves_direct_project_sibling(tmp_path, monkeypatch):
    from lokay.proc import resolve_self_repair_checkout as module
    repo = RepoConfig(name="mikolaj92/lokay", clone_path=tmp_path / "host")
    root = tmp_path / "Developer/lokay"
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: root}, repos=[repo])
    monkeypatch.setattr(module, "load_cfg", lambda _: cfg)
    result = module.resolve(config_path=None, fingerprint="abcdef")
    assert result["worktree"] == str(root / "self-repair__abcdef")
    assert result["managed_root"] == str(root)


@pytest.mark.parametrize("kind", ["root", "ancestor", "destination"])
def test_creation_refuses_symlink_paths_before_git(tmp_path, kind):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "main")
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "project"
    if kind == "ancestor":
        root.symlink_to(outside, target_is_directory=True)
        root = root / "nested"
    elif kind == "root":
        root.symlink_to(outside, target_is_directory=True)
    else:
        root.mkdir()
        (root / "ai__fix__42-title").symlink_to(outside, target_is_directory=True)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: root})
    with pytest.raises(RuntimeError, match="symlink|nofollow|unsafe"):
        ensure_worktree(Runner(), cfg, repo, "ai/fix/42-title", live=True)
    assert list(outside.iterdir()) == []


def test_exact_repair_refuses_symlink_ancestor_before_fetch(tmp_path):
    from lokay.git_worktree import ensure_repair_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "main")
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.symlink_to(outside, target_is_directory=True)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: root / "nested"})
    with pytest.raises(RuntimeError, match="symlink|nofollow|unsafe"):
        ensure_repair_worktree(Runner(), cfg, repo, "ai/fix/42-title", git(clone, "rev-parse", "HEAD").strip(), head_repo=repo.name, live=True)
    assert list(outside.iterdir()) == []


def test_reset_removal_uses_project_managed_root(tmp_path, monkeypatch):
    from lokay import git_worktree as module
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    git(clone, "remote", "add", "origin", str(clone))
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings")
    worktree = worktree_dir(cfg, repo, "ai/fix/42-title")
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(worktree))
    seen = []
    def remove(*args, managed_root):
        seen.append(managed_root)
        return {"ok": False, "error": "test stops reset"}
    monkeypatch.setattr(module, "remove_worktree", remove)
    with pytest.raises(RuntimeError, match="test stops reset"):
        module.ensure_worktree(Runner(), cfg, repo, "ai/fix/42-title", live=True, reset_to_base=True)
    assert seen == [clone.parent]


def test_stale_removal_uses_catalog_project_root(tmp_path, monkeypatch):
    from lokay.proc import remove_stale_worktree_candidate as module
    clone = tmp_path / "project/main"
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", repos=[repo])
    monkeypatch.setattr(module, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(module, "mutations_allowed", lambda **_: None)
    monkeypatch.setattr(module, "live_issue_to_pr_receipts", lambda **_: [])
    monkeypatch.setattr(module, "has_unreadable_issue_to_pr_receipts", lambda: False)
    seen = []
    def remove(*args, managed_root):
        seen.append(managed_root)
        return {"ok": True}
    monkeypatch.setattr(module, "remove_worktree", remove)
    row = {"repo": repo.name, "clone": str(clone), "path": str(clone.parent / "ai__fix__42-title"), "issue": 42}
    assert module.apply({"row": row}, config_path=None, live=True)["applied"]
    assert seen == [clone.parent]


@pytest.mark.parametrize("safe", [True, False])
def test_preflight_checks_actual_project_roots_not_obsolete_global(tmp_path, monkeypatch, safe):
    from lokay import preflight as module
    from lokay import preflight_checks as checks
    clone = make_clone(tmp_path / "project/main")
    root = clone.parent
    if not safe:
        link = tmp_path / "link"
        link.symlink_to(root, target_is_directory=True)
        root = link
    state = tmp_path / "state"
    state.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: root}, repos=[repo], state_path=state / "state.json", worktrees_root=tmp_path / "obsolete", min_free_gb=0)
    monkeypatch.setenv("LOKAY_LOG_DIR", str(logs))
    monkeypatch.setattr(module, "load_config", lambda _: cfg)
    for name in ("check_required_environment", "check_config", "check_pr_review_config", "check_pr_review_credential", "check_repository_catalog_clones", "check_github_authentication", "check_executor_availability"):
        monkeypatch.setattr(checks, name, lambda **_: {"name": "isolated", "ok": True})
    monkeypatch.setattr(module, "_fala_smoke", lambda: (True, "ok"))
    monkeypatch.setattr(module, "_github_git_transport", lambda _: (True, "ok"))
    monkeypatch.setattr(module, "acquire_run_lock", lambda _: True)
    monkeypatch.setattr(module, "trusted_fala_manifest", lambda: None)
    result, _ = module._check(None, set())
    writable = next(row for row in result["findings"] if row["name"] == "writable_runtime_paths")
    assert writable["ok"] is safe


def test_archive_gc_includes_only_configured_project_direct_archives(tmp_path, monkeypatch):
    from lokay.proc import summarize_stale_worktree_reap as module
    import os
    clone = make_clone(tmp_path / "project/main")
    legacy = tmp_path / "legacy"
    old_archive = legacy / "old__repo/.old.lokay-preserved"
    project_archive = clone.parent / ".ai__fix__42.lokay-preserved"
    unrelated = tmp_path / "unrelated/.other.lokay-preserved"
    nested = clone.parent / "human/.nested.lokay-preserved"
    for archive in (old_archive, project_archive, unrelated, nested):
        archive.mkdir(parents=True)
        (archive / "recovery").write_text("keep")
        os.utime(archive, (1, 1))
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", repos=[repo], worktrees_root=legacy)
    monkeypatch.setattr(module, "load_cfg", lambda _: cfg)
    result = module._archive_gc(config_path=None, live=True)
    assert set(result["retained"]) == {str(old_archive), str(project_archive)}
    assert all((archive / "recovery").read_text() == "keep" for archive in (old_archive, project_archive, unrelated, nested))


def test_sibling_creation_keeps_main_checkout_untouched(tmp_path):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    git(clone, "remote", "add", "origin", str(clone))
    (clone / "human-note").write_text("untouched")
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings")
    expected = clone.parent / "ai__fix__42-title"
    assert ensure_worktree(Runner(), cfg, repo, "ai/fix/42-title", live=True) == expected
    assert git(expected, "branch", "--show-current").strip() == "ai/fix/42-title"
    assert git(clone, "branch", "--show-current").strip() == "main"
    assert (clone / "human-note").read_text() == "untouched"


def test_legacy_default_keeps_existing_paths_and_iterator_behavior(tmp_path):
    repo = RepoConfig(name="owner/project", clone_path=tmp_path / "main")
    cfg = Config(worktrees_root=tmp_path / "legacy")
    expected = cfg.worktrees_root / "owner__project/ai__fix__42-title"
    expected.mkdir(parents=True)
    assert worktree_dir(cfg, repo, "ai/fix/42-title") == expected
    assert iter_worktrees(cfg, repo) == [(expected, "ai/fix/42-title")]


def test_iterator_refuses_symlink_project_root(tmp_path):
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    link = tmp_path / "link"
    link.symlink_to(clone.parent, target_is_directory=True)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: link})
    with pytest.raises(RuntimeError, match="unsafe|nofollow"):
        iter_worktrees(cfg, repo)


def test_iterator_rejects_registered_path_replaced_by_foreign_worktree(tmp_path):
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    managed.rename(tmp_path / "preserved")
    foreign = make_clone(tmp_path / "foreign")
    git(foreign, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    cfg = Config(worktrees_layout="clone-siblings")
    repo = RepoConfig(name="owner/project", clone_path=clone)
    assert iter_worktrees(cfg, repo) == []


def test_iterator_rejects_incomplete_registry_without_canonical_main(tmp_path, monkeypatch):
    from dataclasses import replace
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    raw = git(clone, "worktree", "list", "--porcelain", "-z")
    raw = raw.split("\0\0", 1)[1]
    original = Runner.run
    def run(self, spec, **kwargs):
        if "--porcelain" in spec.argv:
            result = original(self, spec, **kwargs)
            return replace(result, stdout=raw)
        return original(self, spec, **kwargs)
    monkeypatch.setattr(Runner, "run", run)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    with pytest.raises(RuntimeError, match="registry"):
        iter_worktrees(Config(worktrees_layout="clone-siblings"), repo)


def test_loaded_clone_parent_symlink_is_not_hidden(tmp_path):
    outside = tmp_path / "outside"
    clone = make_clone(outside / "main")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    config = tmp_path / "config.yaml"
    config.write_text(f"worktrees:\n  layout: clone-siblings\nrepos:\n  - name: owner/project\n    clone_path: {link / 'main'}\n")
    cfg = load_config(config)
    with pytest.raises(RuntimeError, match="nofollow|unsafe"):
        iter_worktrees(cfg, cfg.repos[0])


@pytest.mark.parametrize("value", [[], "bad", {"owner/project": None}, {"owner/project": 42}])
def test_invalid_project_root_map_rejected(tmp_path, value):
    import yaml
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"worktrees": {"layout": "clone-siblings", "project_roots": value}}))
    with pytest.raises(ValueError, match="project_roots"):
        load_config(config)


def test_creation_refuses_canonical_main_destination(tmp_path):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    repo = RepoConfig(name="owner/project", clone_path=clone)
    with pytest.raises(RuntimeError, match="refusing canonical checkout destination"):
        ensure_worktree(Runner(), Config(worktrees_layout="clone-siblings"), repo, "main", live=True)
    assert git(clone, "branch", "--show-current").strip() == "main"


def test_archive_scan_refuses_symlink_ancestor(tmp_path):
    from lokay.proc.prune_preserved_worktree_archives import list_expired_archives
    outside = tmp_path / "outside"
    archive = outside / "project/.recovery.lokay-preserved"
    archive.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    assert list_expired_archives(link / "project", now=10**12, direct=True) == []


def test_remove_boundary_never_removes_canonical_checkout(tmp_path):
    from lokay.git_worktree import remove_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    (clone / "important").write_text("keep")
    result = remove_worktree(Runner(), clone, clone, managed_root=clone.parent)
    assert result["ok"] is False
    assert "canonical" in result["error"]
    assert (clone / "important").read_text() == "keep"


@pytest.mark.parametrize("body", ["worktrees: [broken", "repos: nope", "worktrees:\n  project_roots: null\n"])
def test_invalid_loaded_config_keeps_receipt_occupied(tmp_path, monkeypatch, body):
    import json
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
    config = tmp_path / "config.yaml"
    config.write_text(body)
    monkeypatch.setenv("LOKAY_CONFIG", str(config))
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    receipt = {"repo": "owner/project", "issue": 42, "pid": 999}
    (cycle / "receipt.json").write_text(json.dumps(receipt))
    assert live_issue_to_pr_receipts(cycle, pid_alive=lambda _: True, issue_closed=lambda *_: False) == [receipt]


def test_existing_foreign_checkout_cannot_be_reused(tmp_path):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    git(clone, "remote", "add", "origin", str(clone))
    foreign = make_clone(tmp_path / "foreign")
    managed = clone.parent / "ai__fix__42-title"
    git(foreign, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    repo = RepoConfig(name="owner/project", clone_path=clone)
    with pytest.raises(RuntimeError, match="identity|foreign|canonical"):
        ensure_worktree(Runner(), Config(worktrees_layout="clone-siblings"), repo, "ai/fix/42-title", live=True)


def test_creation_rechecks_parent_after_fetch_ancestor_swap(tmp_path):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "main")
    git(clone, "remote", "add", "origin", str(clone))
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    class SwapRunner(Runner):
        def run_checked(self, spec, **kwargs):
            result = super().run_checked(spec, **kwargs)
            if "fetch" in spec.argv:
                root.rename(tmp_path / "original-project")
                root.symlink_to(outside, target_is_directory=True)
            return result
    repo = RepoConfig(name="owner/project", clone_path=clone)
    cfg = Config(worktrees_layout="clone-siblings", project_worktree_roots={repo.name: root})
    with pytest.raises(RuntimeError, match="unsafe|nofollow|symlink"):
        ensure_worktree(SwapRunner(), cfg, repo, "ai/fix/42-title", live=True)
    assert list(outside.iterdir()) == []


def test_iterator_excludes_symlink_git_identity_file(tmp_path):
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    marker = managed / ".git"
    saved = tmp_path / "git-marker"
    marker.rename(saved)
    marker.symlink_to(saved)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    assert iter_worktrees(Config(worktrees_layout="clone-siblings"), repo) == []


def test_example_documents_opt_in_project_override():
    import yaml
    example = Path(__file__).parents[1] / "config.example.yaml"
    text = example.read_text()
    assert yaml.safe_load(text)["worktrees"]["layout"] == "legacy"
    assert "clone-siblings" in text
    assert "mikolaj92/lokay: ~/Developer/lokay" in text


def test_self_repair_creation_refuses_symlink_ancestor(tmp_path):
    from lokay.proc.create_self_repair_worktree import create
    clone = make_clone(tmp_path / "main")
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink|nofollow|unsafe"):
        create({"worktree": str(root / "nested/self-repair__abc"), "clone": str(clone), "base_sha": git(clone, "rev-parse", "HEAD").strip()})
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("probe", ["--git-common-dir", "symbolic-ref"])
def test_unknown_registered_identity_fails_closed(tmp_path, monkeypatch, probe):
    from dataclasses import replace
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    original = Runner.run
    def run(self, spec, **kwargs):
        result = original(self, spec, **kwargs)
        if probe in spec.argv:
            return replace(result, returncode=1, stdout="", stderr="inspection unavailable")
        return result
    monkeypatch.setattr(Runner, "run", run)
    repo = RepoConfig(name="owner/project", clone_path=clone)
    with pytest.raises(RuntimeError, match="identity"):
        iter_worktrees(Config(worktrees_layout="clone-siblings"), repo)


def test_explicit_receipt_config_overrides_valid_wrong_default(tmp_path, monkeypatch):
    import json
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    cfg = Config(worktrees_layout="clone-siblings", repos=[RepoConfig(name="owner/project", clone_path=clone)])
    wrong = tmp_path / "wrong.yaml"
    wrong.write_text(f"worktrees:\n  root: {tmp_path / 'empty'}\nrepos:\n  - name: owner/project\n    clone_path: {clone}\n")
    monkeypatch.setenv("LOKAY_CONFIG", str(wrong))
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    receipt = {"repo": "owner/project", "issue": 42, "pid": 999}
    (cycle / "receipt.json").write_text(json.dumps(receipt))
    assert live_issue_to_pr_receipts(cycle, cfg=cfg, pid_alive=lambda _: True, issue_closed=lambda *_: False) == [receipt]


def test_reuse_rechecks_identity_after_fetch_swap(tmp_path):
    from lokay.git_worktree import ensure_worktree
    from lokay.runner import Runner
    clone = make_clone(tmp_path / "project/main")
    git(clone, "remote", "add", "origin", str(clone))
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    foreign = make_clone(tmp_path / "foreign")
    class SwapRunner(Runner):
        def run_checked(self, spec, **kwargs):
            result = super().run_checked(spec, **kwargs)
            if "fetch" in spec.argv:
                managed.rename(tmp_path / "saved")
                git(foreign, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
            return result
    repo = RepoConfig(name="owner/project", clone_path=clone)
    with pytest.raises(RuntimeError, match="identity"):
        ensure_worktree(SwapRunner(), Config(worktrees_layout="clone-siblings"), repo, "ai/fix/42-title", live=True)


def test_stale_collection_passes_actual_config_to_receipt_lookup(tmp_path, monkeypatch):
    from lokay.proc import collect_stale_worktree_candidates as module
    cfg = Config(worktrees_layout="clone-siblings")
    monkeypatch.setattr(module, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(module, "load_begin_working", lambda _: ({}, {}))
    monkeypatch.setattr(module, "has_unreadable_issue_to_pr_receipts", lambda: False)
    seen = []
    def receipts(*, cfg):
        seen.append(cfg)
        return []
    monkeypatch.setattr(module, "live_issue_to_pr_receipts", receipts)
    module.collect(pass_dir=str(tmp_path), config_path="explicit.yaml")
    assert seen == [cfg]


def test_stale_removal_rechecks_receipts_with_actual_config(tmp_path, monkeypatch):
    from lokay.proc import remove_stale_worktree_candidate as module
    cfg = Config(worktrees_layout="clone-siblings")
    monkeypatch.setattr(module, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(module, "has_unreadable_issue_to_pr_receipts", lambda: False)
    seen = []
    def receipts(*, cfg):
        seen.append(cfg)
        return [{"repo": "owner/project", "issue": 42}]
    monkeypatch.setattr(module, "live_issue_to_pr_receipts", receipts)
    result = module.apply({"row": {"repo": "owner/project", "issue": 42}}, config_path="explicit.yaml", live=True)
    assert result["applied"] is False
    assert result["row"]["reason"] == "live_issue_to_pr"
    assert seen == [cfg]


@pytest.mark.parametrize("denied", ["worktree", "marker"])
@pytest.mark.parametrize("starting", [False, True])
def test_unreadable_registered_entry_retains_receipt(tmp_path, monkeypatch, denied, starting):
    import json
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
    clone = make_clone(tmp_path / "project/main")
    managed = clone.parent / "ai__fix__42-title"
    git(clone, "worktree", "add", "-b", "ai/fix/42-title", str(managed))
    cfg = Config(worktrees_layout="clone-siblings", repos=[RepoConfig(name="owner/project", clone_path=clone)])
    target = managed if denied == "worktree" else managed / ".git"
    original = Path.stat
    def stat_path(self, *args, **kwargs):
        if self == target:
            raise PermissionError("inspection denied")
        return original(self, *args, **kwargs)
    original_lstat = Path.lstat
    def lstat_path(self, *args, **kwargs):
        if self == target:
            raise PermissionError("inspection denied")
        return original_lstat(self, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", stat_path)
    monkeypatch.setattr(Path, "lstat", lstat_path)
    with pytest.raises(RuntimeError, match="inspect"):
        iter_worktrees(cfg, cfg.repos[0])
    cycle = tmp_path / "cycle"
    cycle.mkdir()
    receipt = {"repo": "owner/project", "issue": 42, "pid": 999}
    if starting:
        receipt["starting"] = True
    (cycle / "receipt.json").write_text(json.dumps(receipt))
    assert live_issue_to_pr_receipts(cycle, cfg=cfg, pid_alive=lambda _: True, issue_closed=lambda *_: False) == [receipt]
