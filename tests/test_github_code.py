"""GitHub code plugin: one target clones and merge-commits. No tasks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.code import (
    CodeContractError,
    CodeSlot,
    CodeTarget,
    GithubCode,
    bind_code,
    load_code,
    parse_code_slot,
    slot_from_repo,
)
from lokay.catalog import CatalogBinding
from lokay.config import Config, RepoConfig
from lokay.runner import CommandResult, CommandSpec


class _Runner:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.calls: list[tuple[str, ...]] = []
        self.list_rows = [
            {
                "number": 7,
                "title": "fix parser",
                "body": "Closes #873",
                "headRefName": "ai/fix/7-parser",
                "headRefOid": "abc123",
                "author": {"login": "mikolaj92"},
                "url": "https://github.com/mikolaj92/lokay/pull/7",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "labels": [],
            }
        ]
        self.view = {
            "number": 7,
            "title": "fix parser",
            "body": "Closes #873",
            "comments": [{"body": "looks good"}],
            "headRefName": "ai/fix/7-parser",
            "url": "https://github.com/mikolaj92/lokay/pull/7",
            "statusCheckRollup": [],
        }
        self.checks_rc = 0
        self.checks_out = "all good"
        self.clone_rc = 0

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        argv = spec.argv
        if len(argv) >= 3 and argv[0] == "gh" and argv[1] == "repo" and argv[2] == "clone":
            dest = Path(argv[-1])
            if self.clone_rc == 0:
                dest.mkdir(parents=True, exist_ok=True)
            return CommandResult(spec=spec, executed=live, returncode=self.clone_rc, stdout="", stderr="")
        if "pr" in argv and "list" in argv:
            return CommandResult(
                spec=spec,
                executed=live,
                returncode=0,
                stdout=json.dumps(self.list_rows),
            )
        if "pr" in argv and "view" in argv:
            return CommandResult(
                spec=spec, executed=live, returncode=0, stdout=json.dumps(self.view)
            )
        if "pr" in argv and "checks" in argv:
            return CommandResult(
                spec=spec,
                executed=live,
                returncode=self.checks_rc,
                stdout=self.checks_out,
            )
        return CommandResult(spec=spec, executed=live, returncode=0, stdout="", stderr="")

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError(f"command failed ({result.returncode}): {spec.display()}")
        return result


def _cfg(tmp_path: Path, *, plugin: str = "github", target: str = "mikolaj92/lokay") -> Config:
    clone = tmp_path / "lokay"
    return Config(
        mode="live",
        branch_prefix="ai/fix",
        merge_enabled=True,
        gh_survey_pace_ms=0,
        worktrees_root=tmp_path / "worktrees",
        repos=[
            RepoConfig(
                name="mikolaj92/lokay",
                clone_path=clone,
                code=CatalogBinding(plugin, target),
            )
        ],
    )


def _host(tmp_path: Path, runner: _Runner, cfg: Config) -> GithubCode:
    slot = slot_from_repo(cfg.repos[0])
    return GithubCode.from_slot(slot, runner=runner, config=cfg, live=True)


def test_catalog_code_plugin_github_defaults_from_old_row(tmp_path: Path) -> None:
    slot = parse_code_slot(
        {"name": "mikolaj92/lokay", "clone_path": str(tmp_path / "lokay")},
        default_name="mikolaj92/lokay",
        default_clone=tmp_path / "lokay",
    )
    assert slot.plugin == "github"
    assert slot.target == "mikolaj92/lokay"
    assert slot.clone_path == tmp_path / "lokay"


def test_catalog_code_field_loads_github_plugin(tmp_path: Path) -> None:
    slot = parse_code_slot(
        {
            "code": {
                "plugin": "github",
                "target": "mikolaj92/reviewkit",
                "clone_path": str(tmp_path / "reviewkit"),
            }
        },
        default_name="ignored",
        default_clone=tmp_path / "ignored",
    )
    assert slot == CodeSlot(
        plugin="github",
        target="mikolaj92/reviewkit",
        clone_path=tmp_path / "reviewkit",
    )


def test_unknown_code_plugin_fails_at_load(tmp_path: Path) -> None:
    with pytest.raises(CodeContractError, match="unknown code plugin"):
        parse_code_slot(
            {"code": {"plugin": "azure", "target": "org/project/repo"}},
            default_name="org/project/repo",
            default_clone=tmp_path / "azure",
        )


def test_github_plugin_clones_and_merges_from_one_target(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    runner = _Runner(tmp_path)
    host = _host(tmp_path, runner, cfg)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert contract.target.plugin == "github"
    assert contract.repo.target == contract.pr.target == contract.target
    assert contract.target.id == "mikolaj92/lokay"

    cloned = contract.repo.clone()
    assert cloned == tmp_path / "lokay"
    assert cloned.is_dir()
    clone_calls = [argv for argv in runner.calls if argv[:3] == ("gh", "repo", "clone")]
    assert clone_calls
    assert "mikolaj92/lokay" in clone_calls[0]
    assert str(tmp_path / "lokay") in clone_calls[0]

    head = contract.repo.branch("ai/fix/7-parser")
    assert head == "ai/fix/7-parser"

    rows = contract.pr.list_open()
    assert [row.number for row in rows] == [7]
    assert rows[0].head == "ai/fix/7-parser"
    assert rows[0].target == host.target

    merged = contract.pr.merge_commit(7)
    assert merged.state == "merged"
    assert merged.merge_method == "merge"
    assert merged.merge_method != "squash"
    merge_calls = [argv for argv in runner.calls if "merge" in argv]
    assert merge_calls
    assert "--merge" in merge_calls[0]
    assert "--squash" not in merge_calls[0]
    assert "7" in merge_calls[0]
    assert "mikolaj92/lokay" in merge_calls[0]


def test_load_code_from_catalog_field(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    runner = _Runner(tmp_path)
    contract = load_code(slot_from_repo(cfg.repos[0]), runner=runner, config=cfg, live=True)
    assert contract.target == CodeTarget(plugin="github", id="mikolaj92/lokay")
    contract.repo.clone()
    contract.pr.merge_commit(7)
    assert any(argv[:3] == ("gh", "repo", "clone") for argv in runner.calls)
    assert any("--merge" in argv for argv in runner.calls)


def test_github_host_has_no_tasks(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    host = _host(tmp_path, _Runner(tmp_path), cfg)
    for name in (
        "list_issues",
        "get_issue",
        "list_tasks",
        "comment_issue",
        "mark_issue",
        "close_issue",
        "tasks",
        "issues",
    ):
        assert not hasattr(host, name)
        assert not hasattr(host.repo, name)
        assert not hasattr(host.pr, name)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert not hasattr(contract, "tasks")
    assert not hasattr(contract, "issues")


def test_github_pr_list_get_checks_comment_close(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    runner = _Runner(tmp_path)
    host = _host(tmp_path, runner, cfg)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    rows = contract.pr.list_open()
    assert rows[0].number == 7
    one = contract.pr.get(7)
    assert one.title == "fix parser"
    assert one.target == host.target
    checks = contract.pr.checks(7)
    assert checks.status == "passed"
    assert checks.green is True
    noted = contract.pr.comment(7, "ship it")
    assert "ship it" in noted.comments
    closed = contract.pr.close(7)
    assert closed.state == "closed"
    assert closed.merge_method is None


def test_pr_and_clone_atoms_do_not_import_gh_prs_or_git() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc"
    atoms = (
        "list_prs.py",
        "list_open_prs.py",
        "pr_merge.py",
        "pr_close.py",
        "pr_checks.py",
        "repos_clone_missing.py",
        "worktree_add.py",
    )
    banned = (
        "from lokay.gh_prs",
        "import lokay.gh_prs",
        "from lokay.git_worktree",
        "from lokay.git_branch",
        "from lokay.git_commit",
        "gh_spec",
    )
    for name in atoms:
        text = (root / name).read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{name} must not contain {token}"
        assert "load_code" in text or "GithubCode" in text or "slot_from_repo" in text
