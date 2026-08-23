"""Auto-split planning + issue_split atom (dry / mocked gh)."""

from __future__ import annotations



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


def test_issue_split_cli_invokes_authored_subflow(monkeypatch, tmp_path, capsys):
    cfg=tmp_path/"config.yaml"; cfg.write_text("mode: dry-run\nrepos: []\nexecutor: {enabled: false}\nmerge: {enabled: false}\nworktrees: {root: /tmp/wt}\nstate: {path: /tmp/state.jsonl}\n")
    calls=[]
    monkeypatch.setattr(atom,"run_path",lambda **kwargs:calls.append(kwargs) or {"ok":True,"applied":False,"children":[]})
    code=atom.main(["--config",str(cfg),"--repo","mikolaj92/lokay","--issue","9","--reason","too_many_checkboxes"])
    assert code == 0
    assert calls[0]["path_id"] == "issue_split"
    assert calls[0]["extra_inputs"] == {"split_reason":"too_many_checkboxes"}


def test_create_split_child_is_one_indexed_effect(monkeypatch):
    from lokay.proc.create_issue_split_child import create
    created=[]
    monkeypatch.setattr("lokay.proc.create_issue_split_child.create_issue",lambda *_args,**kwargs:created.append(kwargs) or {"number":10})
    plan={"children":[{"title":"one","body":"body","source":"checkbox"},{"title":"two","body":"body","source":"checkbox"}]}
    out=create(runner=object(),repo="a/b",plan=plan,slot=2,live=True)
    assert out["child"]["number"] == 10
    assert created[0]["title"] == "two"
    assert create(runner=object(),repo="a/b",plan=plan,slot=3,live=True)["route"] == "absent"
