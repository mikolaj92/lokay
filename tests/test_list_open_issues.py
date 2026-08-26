from types import SimpleNamespace

from lokay.gh_rate import parse_survey_list
from lokay.proc.list_open_issues import run
from lokay.proc.select_next_issue import select
from lokay.proc.summarize_issues import summarize


class _Cfg:
    def active_repos(self):
        return [SimpleNamespace(name="o/r")]


def test_empty_list_is_skip_not_error(monkeypatch):
    monkeypatch.setattr("lokay.proc.list_open_issues.load_cfg", lambda _args: _Cfg())
    monkeypatch.setattr("lokay.proc.list_open_issues.runner", lambda: object())
    monkeypatch.setattr(
        "lokay.proc.list_open_issues.list_ready_issues",
        lambda *_a, **_k: [],
    )
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "empty"
    assert out["issues"] == []


def test_overflow_keeps_page_and_does_not_fail(monkeypatch):
    issue = SimpleNamespace(repo="o/r", number=9, title="x", labels=["bug"])
    monkeypatch.setattr("lokay.proc.list_open_issues.load_cfg", lambda _args: _Cfg())
    monkeypatch.setattr("lokay.proc.list_open_issues.runner", lambda: object())

    def fake_ready(*_a, live, on_cap="fail"):
        assert on_cap == "keep"
        return [issue]

    monkeypatch.setattr("lokay.proc.list_open_issues.list_ready_issues", fake_ready)
    monkeypatch.setattr("lokay.proc.list_open_issues.survey_list_cap", lambda: 1)
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["route"] == "listed"
    assert out["overflow"] is True
    assert out["issues"][0]["issue"] == 9


def test_overflow_without_rows_is_skip(monkeypatch):
    monkeypatch.setattr("lokay.proc.list_open_issues.load_cfg", lambda _args: _Cfg())
    monkeypatch.setattr("lokay.proc.list_open_issues.runner", lambda: object())

    def boom(*_a, **_k):
        raise RuntimeError("ready-issue survey on o/r hit the 1 newest-first cap")

    monkeypatch.setattr("lokay.proc.list_open_issues.list_ready_issues", boom)
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "overflow"


def test_sito_picks_one_and_leaves_leftover():
    listed = {
        "issues": [
            {"repo": "o/r", "issue": 2, "title": "a"},
            {"repo": "o/r", "issue": 3, "title": "b"},
        ]
    }
    out = select(listed)
    assert out["route"] == "issue" and out["issue"] == 2 and out["leftover"] == 1


def test_listed_skip_is_none():
    assert select({"route": "skip", "reason": "overflow", "skipped": True})["route"] == "none"


def test_summarize_writes_receipt_on_empty(tmp_path):
    out = summarize(
        {"route": "none", "reason": "empty"},
        {"route": "skip", "reason": "no_issue"},
        {},
        pass_dir=str(tmp_path),
    )
    assert out["ok"] is True
    assert out["result"]["route"] == "skip"
    assert tmp_path.joinpath("issues-receipt.json").is_file()


def test_parse_keep_does_not_raise():
    rows = parse_survey_list(
        '[{"number": 1}, {"number": 2}]',
        kind="ready-issue",
        repo="o/r",
        cap=2,
        on_cap="keep",
    )
    assert len(rows) == 2
