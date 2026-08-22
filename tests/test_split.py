"""Auto-split planning + issue_split atom (dry / mocked gh)."""

from __future__ import annotations

import json

import pytest

from lokay.models import Issue
from lokay.proc import issue_split as atom
from lokay.split import plan_split


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=9,
        title="Big epic tracker",
        body="",
        labels=[],
        assignees=[],
        url="https://example.com/9",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_plan_split_from_checkboxes():
    body = "\n".join(f"- [ ] deliverable {i} with enough text" for i in range(6))
    plan = plan_split(_issue(body=body), reason="too_many_checkboxes")
    assert plan is not None
    assert 2 <= len(plan.children) <= 5
    assert all(c.source == "checkbox" for c in plan.children)
    assert "Parent" in plan.children[0].body
    assert "#9" in plan.children[0].body


def test_plan_split_inventory_without_parts():
    plan = plan_split(
        _issue(
            title="Inventory everything in pad",
            body="Please inventory everything across the org.\n" * 2,
        ),
        reason="inventory_everything",
    )
    assert plan is not None
    assert len(plan.children) == 2
    assert plan.close_parent is True
    assert plan.parent_tracker_label == "ai:tracker"


def test_plan_split_fails_closed_without_parts_for_title_only():
    plan = plan_split(
        _issue(title="Vague ask here", body="todo"),
        reason="title_only_body",
    )
    assert plan is None


def test_issue_split_atom_creates_children(monkeypatch, tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: live
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )

    issue = _issue(
        body="\n".join(f"- [ ] slice {i} concrete work item" for i in range(4)),
        labels=["ai:ready"],
    )
    created: list[dict] = []

    monkeypatch.setenv("LOKAY_OFFLINE", "0")
    monkeypatch.setattr(atom, "get_issue", lambda *a, **k: issue)
    monkeypatch.setattr(atom, "mutations_allowed", lambda **k: True)

    def fake_create(runner, *, repo, title, body, labels=None, live):
        n = 100 + len(created)
        row = {"number": n, "url": f"https://example.com/{n}", "title": title, "repo": repo}
        created.append(row)
        return row

    monkeypatch.setattr(atom, "create_issue", fake_create)
    monkeypatch.setattr(atom, "add_issue_labels", lambda *a, **k: None)
    monkeypatch.setattr(atom, "remove_issue_labels", lambda *a, **k: None)
    monkeypatch.setattr(atom, "comment_issue", lambda *a, **k: None)
    monkeypatch.setattr(atom, "close_issue", lambda *a, **k: None)
    monkeypatch.setattr(atom, "runner", lambda: object())

    code = atom.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "9",
            "--intake-decision",
            "split",
            "--reason",
            "too_many_checkboxes",
        ]
    )
    assert code == 0
    import json

    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True
    assert out["applied"] is True
    assert out["decision"] == "split"
    assert out["parent_tracker"] is True
    assert len(out["children"]) == 4
    assert len(created) == 4
    assert all(child["repo"] == "mikolaj92/lokay" for child in created)


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_issue_split_skips_product_repo_without_config_or_gh(
    repo, monkeypatch, capsys
):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("product repositories must not load config or call GitHub")

    monkeypatch.setattr(atom, "load_cfg", fail_if_called)
    monkeypatch.setattr(atom, "runner", fail_if_called)
    monkeypatch.setattr(atom, "get_issue", fail_if_called)
    monkeypatch.setattr(atom, "create_issue", fail_if_called)
    monkeypatch.setattr(atom, "add_issue_labels", fail_if_called)
    monkeypatch.setattr(atom, "remove_issue_labels", fail_if_called)
    monkeypatch.setattr(atom, "comment_issue", fail_if_called)
    monkeypatch.setattr(atom, "close_issue", fail_if_called)

    assert atom.main(["--repo", repo, "--issue", "9", "--force", "--live"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "applied": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 9,
        "children": [],
    }


def test_issue_split_skips_when_not_split_decision(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
executor:
  enabled: false
merge:
  enabled: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    code = atom.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "9",
            "--intake-decision",
            "ready",
        ]
    )
    assert code == 0
    import json

    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["skipped"] is True
    assert out["children"] == []
