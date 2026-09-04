"""GitHub tasks plugin: catalog issues.plugin: github walks list/get paths."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from lokay.config import load_config
from lokay.proc import apply_issue_mark, get_issue, list_issues, list_open_issues
from lokay.tasks import MARKS, TaskId, sito_park
from lokay.github_tasks import GitHubTasks, issue_to_task, load_tasks


def _imports(mod) -> set[str]:
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def _issue(
    number: int,
    *,
    repo: str = "mikolaj92/lokay",
    title: str = "",
    body: str = "",
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    state: str = "OPEN",
    author: str = "",
    comments: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        repo=repo,
        number=number,
        title=title,
        body=body,
        labels=list(labels or []),
        assignees=list(assignees or []),
        url=f"https://github.com/{repo}/issues/{number}",
        state=state,
        author=author,
        comments=list(comments or []),
    )


class RecordedGh:
    """Recorded gh_issues. No sockets."""

    def __init__(self, items: list[SimpleNamespace]) -> None:
        self.items = {int(row.number): row for row in items}
        self.calls: list[str] = []

    def list_ready(self, runner, config, repo, *, live, on_cap="fail"):
        self.calls.append("list")
        target = getattr(repo, "name", None) or "mikolaj92/lokay"
        return [
            row
            for row in self.items.values()
            if row.repo == target and str(row.state).upper() != "CLOSED"
        ]

    def view(self, runner, config, repo, number, *, live):
        self.calls.append("get")
        row = self.items.get(int(number))
        if row is None or row.repo != repo:
            return None
        return row

    def comment(self, runner, repo, number, body, *, live):
        self.calls.append("comment")
        row = self.items[int(number)]
        row.comments.append(body)

    def add_labels(self, runner, repo, number, labels, *, live):
        self.calls.append("add")
        row = self.items[int(number)]
        have = set(row.labels)
        row.labels = list(row.labels) + [x for x in labels if x not in have]

    def remove_labels(self, runner, repo, number, labels, *, live):
        self.calls.append("remove")
        row = self.items[int(number)]
        drop = set(labels)
        row.labels = [x for x in row.labels if x not in drop]


def _source(rec: RecordedGh, *, target: str = "mikolaj92/lokay") -> GitHubTasks:
    return GitHubTasks(
        row={"issues": {"plugin": "github", "target": target}},
        target=target,
        runner=object(),
        config=SimpleNamespace(ready_label="ai:ready", blocked_label="ai:blocked"),
        live=True,
    )


def _patch_gh(monkeypatch: pytest.MonkeyPatch, rec: RecordedGh) -> None:
    monkeypatch.setattr("lokay.github_tasks.list_ready_issues", rec.list_ready)
    monkeypatch.setattr("lokay.github_tasks.view_issue", rec.view)
    monkeypatch.setattr("lokay.github_tasks.comment_issue", rec.comment)
    monkeypatch.setattr("lokay.github_tasks.add_issue_labels", rec.add_labels)
    monkeypatch.setattr("lokay.github_tasks.remove_issue_labels", rec.remove_labels)


def test_catalog_row_loads_github_and_ignores_code_prs(monkeypatch: pytest.MonkeyPatch):
    rec = RecordedGh([_issue(12, title="first")])
    _patch_gh(monkeypatch, rec)
    row = {
        "issues": {"plugin": "github", "target": "mikolaj92/lokay"},
        "code": {"plugin": "github", "target": "mikolaj92/lokay", "clone_path": "/tmp/lokay"},
        "prs": {"plugin": "azure", "target": "contoso/board"},
    }
    source = load_tasks(
        row,
        runner=object(),
        config=SimpleNamespace(ready_label="ai:ready", blocked_label="ai:blocked"),
        live=True,
    )
    assert isinstance(source, GitHubTasks)
    assert source.plugin == "github"
    assert source.target == "mikolaj92/lokay"
    listed = source.list_open()
    assert [task.number for task in listed] == [12]
    assert all(task.plugin == "github" and task.target == "mikolaj92/lokay" for task in listed)
    assert rec.calls == ["list"]


def test_list_get_comment_mark_walks_gh_issues(monkeypatch: pytest.MonkeyPatch):
    rec = RecordedGh(
        [
            _issue(12, title="first", body="do it", assignees=["lokay"]),
            _issue(15, title="second"),
            _issue(9, title="done", state="CLOSED"),
        ]
    )
    _patch_gh(monkeypatch, rec)
    source = _source(rec)
    listed = source.list_open()
    assert [task.number for task in listed] == [12, 15]
    one = source.get(listed[0].id)
    assert one is not None
    assert one.id == TaskId("github", "mikolaj92/lokay", 12)
    assert one.title == "first"
    assert one.body == "do it"
    assert one.assignees == ["lokay"]
    assert one.state == "OPEN"

    source.comment(one.id, "working")
    ready = source.mark(one.id, "ready")
    assert ready.mark == "ready"
    assert ready.state == "OPEN"
    assert "ai:ready" in ready.labels
    assert source.get(one.id).comments == ["working"]
    assert "list" in rec.calls
    assert "get" in rec.calls


def test_mark_park_ready_blocked_never_closes(monkeypatch: pytest.MonkeyPatch):
    rec = RecordedGh([_issue(8, title="open work", labels=["ai:ready"])])
    _patch_gh(monkeypatch, rec)
    source = _source(rec)
    identity = TaskId("github", "mikolaj92/lokay", 8)
    for kind in sorted(MARKS):
        out = source.mark(identity, kind)
        assert out.mark == kind
        assert out.state == "OPEN"
        assert out.state != "CLOSED"
    assert source.get(identity).state == "OPEN"
    assert [task.number for task in source.list_open()] == [8]


def test_sito_parks_foreign_open_task_and_does_not_close(monkeypatch: pytest.MonkeyPatch):
    rec = RecordedGh(
        [
            _issue(
                4990,
                repo="mikolaj92/Temida",
                title="someone else's work",
                assignees=["PSyron"],
                labels=["ai:ready"],
            )
        ]
    )
    _patch_gh(monkeypatch, rec)
    source = _source(rec, target="mikolaj92/Temida")
    identity = TaskId("github", "mikolaj92/Temida", 4990)
    out = sito_park(source, identity, "foreign_assignee")
    assert out.state == "OPEN"
    assert out.mark == "park"
    assert "ai:blocked" in out.labels
    assert "ai:ready" not in out.labels
    assert any("Parked" in body for body in out.comments)
    assert source.get(identity).state != "CLOSED"
    assert [task.number for task in source.list_open()] == [4990]


def test_source_has_no_pr_or_repo():
    source = _source(RecordedGh([]))
    names = {name for name in dir(source) if not name.startswith("_")}
    forbidden = {
        "branch",
        "clone",
        "close",
        "git",
        "list_prs",
        "merge",
        "pr",
        "prs",
        "repo",
        "worktree",
    }
    assert names.isdisjoint(forbidden)
    assert not hasattr(source, "list_prs")
    assert not hasattr(source, "merge")
    assert not hasattr(source, "clone")
    assert not hasattr(source, "close")
    assert not hasattr(source, "repo")
    assert "repo" not in source.__dict__
    assert not hasattr(GitHubTasks, "list_prs")
    assert not hasattr(GitHubTasks, "merge")


def test_get_is_identity_bound_and_unknown_plugin_does_not_load(monkeypatch: pytest.MonkeyPatch):
    rec = RecordedGh([_issue(1, title="open"), _issue(2, title="done", state="CLOSED")])
    _patch_gh(monkeypatch, rec)
    source = _source(rec)
    assert source.get(TaskId("github", "mikolaj92/lokay", 2)).state == "CLOSED"
    assert source.get(TaskId("azure", "mikolaj92/lokay", 1)) is None
    assert source.get(TaskId("github", "other/repo", 1)) is None
    with pytest.raises(KeyError):
        source.comment(TaskId("azure", "mikolaj92/lokay", 1), "no")
    with pytest.raises(ValueError):
        source.mark(TaskId("github", "mikolaj92/lokay", 1), "close")
    with pytest.raises(ValueError, match="not github"):
        load_tasks(
            {"issues": {"plugin": "azure", "target": "contoso/board"}},
            runner=object(),
            config=SimpleNamespace(),
            live=True,
        )


def test_issue_to_task_maps_assignees() -> None:
    task = issue_to_task(
        _issue(5072, repo="mikolaj92/Temida", assignees=["PSyron"], author="PSyron"),
        plugin="github",
        target="mikolaj92/Temida",
    )
    assert task.assignees == ["PSyron"]
    assert task.id == TaskId("github", "mikolaj92/Temida", 5072)


def test_task_atoms_do_not_import_gh_issues() -> None:
    for mod in (list_issues, list_open_issues, get_issue, apply_issue_mark):
        imported = _imports(mod)
        assert "lokay.gh_issues" not in imported
        assert "gh_issues" not in imported


def test_catalog_issues_plugin_github_walks_list_and_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "name": "mikolaj92/lokay",
        "clone_path": str(tmp_path / "lokay"),
        "issues": {"plugin": "github", "target": "mikolaj92/lokay"},
        "code": {"plugin": "github", "target": "mikolaj92/lokay"},
    }
    cat = tmp_path / "repos.yaml"
    cat.write_text(yaml.safe_dump({"repos": [row]}), encoding="utf-8")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"mode: dry-run\nrepos_file: {cat.name}\n", encoding="utf-8")
    rec = RecordedGh(
        [_issue(865, title="GitHub tasks", assignees=["mikolaj92"], labels=["ai:ready"])]
    )
    _patch_gh(monkeypatch, rec)

    out = list_open_issues.run(config_path=str(cfg_path), live=True)
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["issues"][0]["issue"] == 865
    assert out["issues"][0]["assignees"] == ["mikolaj92"]
    assert out["issues"][0]["repo"] == "mikolaj92/lokay"

    monkeypatch.setattr(get_issue, "load_cfg", lambda _args: load_config(cfg_path))
    monkeypatch.setattr(get_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(get_issue, "runner", lambda: object())
    assert get_issue.main(["--repo", "mikolaj92/lokay", "--issue", "865", "--live"]) == 0
    assert rec.calls[0] == "list"
    assert "get" in rec.calls
