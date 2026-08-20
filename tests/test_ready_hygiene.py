from __future__ import annotations

from types import SimpleNamespace

from lokay.models import Issue
from lokay.proc.ready_hygiene import run_ready_hygiene


def _issue(number: int, labels: list[str]) -> Issue:
    return Issue(repo="mikolaj92/lokay", number=number, title="x", body="", labels=labels, assignees=["mikolaj92"], url="")


def test_ready_hygiene_removes_only_orphan_ready(monkeypatch):
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        mode="live",
        active_repos=lambda: [SimpleNamespace(name="mikolaj92/lokay")],
    )
    removed = []
    monkeypatch.setattr("lokay.proc.ready_hygiene.load_cfg", lambda _args: cfg)
    monkeypatch.setattr("lokay.proc.ready_hygiene.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr("lokay.proc.ready_hygiene.runner", lambda *_args: object())
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.list_labeled_issues",
        lambda *_args, **_kwargs: [_issue(1, ["ai:ready"]), _issue(2, ["ai:ready", "work:ready"])],
    )
    monkeypatch.setattr(
        "lokay.proc.ready_hygiene.remove_issue_labels",
        lambda _run, repo, number, labels, *, live: removed.append((repo, number, labels, live)),
    )

    out = run_ready_hygiene(config_path=None, live=True)

    assert out["cleaned_count"] == 1
    assert removed == [("mikolaj92/lokay", 1, ["ai:ready"], True)]
