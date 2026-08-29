from types import SimpleNamespace

from lokay.proc.list_open_issues import facts, run


class _Cfg:
    def active_repos(self):
        return [SimpleNamespace(name="o/r")]


def _patch_list(monkeypatch, listed, *, cap=None):
    monkeypatch.setattr("lokay.proc.list_open_issues.load_cfg", lambda _args: _Cfg())
    monkeypatch.setattr("lokay.proc.list_open_issues.runner", lambda: object())

    def fake_ready(*_a, live, on_cap="fail", **kw):
        assert "label" not in kw
        assert on_cap == "keep"
        return listed

    monkeypatch.setattr("lokay.github_tasks.list_ready_issues", fake_ready)
    if cap is not None:
        monkeypatch.setattr("lokay.proc.list_open_issues.survey_list_cap", lambda: cap)


def test_facts_are_not_a_skip_route(monkeypatch):
    _patch_list(monkeypatch, [])
    out = facts(config_path=None, live=True)
    assert out == {
        "issues": [],
        "count": 0,
        "overflow": False,
        "assignee": "mikolaj92",
    }
    assert "route" not in out
    assert "ok" not in out


def test_run_wraps_facts_as_ok_envelope(monkeypatch):
    _patch_list(monkeypatch, [])
    out = run(config_path=None, live=True)
    assert out == {
        "ok": True,
        "issues": [],
        "count": 0,
        "overflow": False,
        "assignee": "mikolaj92",
    }
    assert "route" not in out
    assert "skipped" not in out


def test_labels_are_not_a_gate(monkeypatch):
    issue = SimpleNamespace(repo="o/r", number=4, title="x", labels=["bug"])
    _patch_list(monkeypatch, [issue])
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["issues"][0] == {
        "repo": "o/r",
        "issue": 4,
        "title": "x",
        "labels": ["bug"],
        "assignees": [],
    }
    assert out["assignee"] == "mikolaj92"
    assert "work:ready" not in out["issues"][0]["labels"]
    assert "ai:ready" not in out["issues"][0]["labels"]


def test_facts_carry_assignees_and_mill(monkeypatch):
    issue = SimpleNamespace(
        repo="Temida/Temida",
        number=5072,
        title="x",
        labels=[],
        assignees=["PSyron"],
    )
    _patch_list(monkeypatch, [issue])
    out = run(config_path=None, live=True)
    assert out["issues"][0]["assignees"] == ["PSyron"]
    assert out["assignee"] == "mikolaj92"


def test_overflow_keeps_page_and_does_not_fail(monkeypatch):
    issue = SimpleNamespace(repo="o/r", number=9, title="x", labels=["bug"])
    _patch_list(monkeypatch, [issue], cap=1)
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["overflow"] is True
    assert out["issues"][0]["issue"] == 9
    assert "route" not in out


def test_dry_run_does_not_claim_overflow(monkeypatch):
    issue = SimpleNamespace(repo="o/r", number=9, title="x", labels=[])
    _patch_list(monkeypatch, [issue], cap=1)
    out = run(config_path=None, live=False)
    assert out["ok"] is True
    assert out["overflow"] is False
    assert out["count"] == 1
