"""A single-repo canary must not fan a department list across the catalog."""

from types import SimpleNamespace

import pytest

from lokay.proc import list_open_issues, list_open_prs
from lokay.proc.scoped_active_repos import UnknownRepoScope
from lokay.tasks import Task


def _cfg(names):
    repos = [SimpleNamespace(name=name) for name in names]
    return SimpleNamespace(active_repos=lambda: repos, assignee="mikolaj92", state_path="", branch_prefix="ai/fix")


def test_issue_list_contacts_only_the_scoped_repo(monkeypatch):
    seen = []
    cfg = _cfg(["o/a", "o/b"])
    monkeypatch.setenv("LOKAY_REPO_SCOPE", "o/a")
    monkeypatch.setattr(list_open_issues, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(list_open_issues, "runner", lambda: object())
    monkeypatch.setattr(
        list_open_issues,
        "load_tasks",
        lambda repo, **_: seen.append(repo.name) or SimpleNamespace(
            list_open=lambda: [Task("github", repo.name, 1, title="t")]
        ),
    )
    page = list_open_issues.run(config_path=None, live=True)
    assert seen == ["o/a"]
    assert [row["repo"] for row in page["issues"]] == ["o/a"]


def test_pr_list_contacts_only_the_scoped_repo(monkeypatch):
    seen = []
    cfg = _cfg(["o/a", "o/b"])
    monkeypatch.setenv("LOKAY_REPO_SCOPE", "o/a")
    monkeypatch.setattr(list_open_prs, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(list_open_prs, "runner", lambda: object())

    def load_code(repo, **_):
        seen.append(repo.name)
        change = SimpleNamespace(target=SimpleNamespace(id=repo.name), number=7, title="p", head="ai/fix/7", head_sha="a" * 40)
        return SimpleNamespace(pr=SimpleNamespace(list_open=lambda: [change]))

    monkeypatch.setattr(list_open_prs, "load_code", load_code)
    monkeypatch.setattr("lokay.proc.delivery_closeout.pending", lambda _path: [])
    page = list_open_prs.run(config_path=None, live=True)
    assert seen == ["o/a"]
    assert [row["repo"] for row in page["prs"]] == ["o/a"]


def test_unknown_scope_lists_nothing(monkeypatch):
    cfg = _cfg(["o/a", "o/b"])
    monkeypatch.setenv("LOKAY_REPO_SCOPE", "o/missing")
    monkeypatch.setattr(list_open_issues, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(list_open_issues, "load_tasks", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("source contacted")))
    with pytest.raises(UnknownRepoScope):
        list_open_issues.facts(config_path=None, live=True)


def test_empty_scope_keeps_the_full_catalog(monkeypatch):
    seen = []
    cfg = _cfg(["o/a", "o/b"])
    monkeypatch.delenv("LOKAY_REPO_SCOPE", raising=False)
    monkeypatch.setattr(list_open_issues, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(list_open_issues, "runner", lambda: object())
    monkeypatch.setattr(
        list_open_issues,
        "load_tasks",
        lambda repo, **_: seen.append(repo.name) or SimpleNamespace(list_open=lambda: []),
    )
    list_open_issues.run(config_path=None, live=False)
    assert seen == ["o/a", "o/b"]
