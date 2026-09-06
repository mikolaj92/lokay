"""Source ordering must not make the newest host kit starve its foundations."""

from types import SimpleNamespace

from lokay.proc import list_open_issues
from lokay.proc.select_next_issue import select
from lokay.tasks import Task


def test_open_page_keeps_catalog_order_and_oldest_issue_first(monkeypatch):
    repos = [SimpleNamespace(name="mikolaj92/app-factory"), SimpleNamespace(name="mikolaj92/other")]
    pages = {
        repos[0].name: [Task("github", repos[0].name, number, labels=["ai:ready"])
                        for number in (84, 83, 82, 81, 80, 79)],
        repos[1].name: [Task("github", repos[1].name, 1, labels=["ai:ready"])],
    }
    cfg = SimpleNamespace(active_repos=lambda: repos, assignee="mikolaj92")
    monkeypatch.setattr(list_open_issues, "load_cfg", lambda _: cfg)
    monkeypatch.setattr(list_open_issues, "runner", lambda: object())
    monkeypatch.setattr(list_open_issues, "load_tasks", lambda repo, **_: SimpleNamespace(list_open=lambda: pages[repo.name]))
    page = list_open_issues.run(config_path=None, live=True)
    assert [(row["repo"], row["issue"]) for row in page["issues"]] == [
        *((repos[0].name, number) for number in range(79, 85)),
        (repos[1].name, 1),
    ]
    assert select(page, occupied=set())["issue"] == 79
    assert [task.number for task in pages[repos[0].name]] == [84, 83, 82, 81, 80, 79]
