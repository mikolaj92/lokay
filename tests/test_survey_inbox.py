"""Contracts for minimal inbox-survey processes."""

from pathlib import Path
from lokay.passkit import io as pass_io


def test_classification_skips_blocked_issue():
    from lokay.proc.classify_inbox_repo_issues import classify

    prepared = {"stuck": {"issues": {"owner/repo#1": {"blocked": True}}}}
    out = classify(
        prepared,
        {"route": "survey", "repo": "owner/repo"},
        {"route": "listed", "issues": [{"number": 1}, {"number": 2}]},
    )
    assert out["issues"] == [{"number": 2}] and out["blocked"] == [1]


def test_failed_listing_increments_probe_error():
    from lokay.proc.reduce_inbox_survey import reduce_state

    from lokay.proc.record_inbox_repo_result import record

    row = record(
        {"mini_repo": "mikolaj92/lokay"},
        {"repo": "owner/repo"},
        {"ok": True, "repo": "owner/repo", "route": "failed", "listed": {"ok": False}},
    )
    out = reduce_state(
        prepared={}, rows=[row], working={"actions": [], "survey_errors": 0}
    )["state"]
    assert out["inbox_survey_failed"] == ["owner/repo"] and out["survey_errors"] == 1


def test_catalog_overflow_is_fail_closed(tmp_path):
    from lokay.proc.prepare_inbox_survey import prepare

    pd = tmp_path / "pass"
    pd.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pd), {"repos": [f"o/r{i}" for i in range(31)]}
    )
    pass_io.write_json(pass_io.working_path(pd), {})
    assert prepare(pass_dir=str(pd), slot_count=30)["ok"] is False


def test_survey_inbox_subflow_uses_handful_of_ticks():
    from lokay.proc.survey_inbox_subflow import run
    import inspect

    source = inspect.getsource(run)
    assert "max_ticks=16" in source


def test_catalog_counts_labeled_undecided_as_remaining_inbox(tmp_path, monkeypatch):
    from lokay.proc import inbox_survey_catalog

    pd = tmp_path / "pass"
    pd.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pd),
        {"repos": ["mikolaj92/Temida", "mikolaj92/Fala"], "stuck": {"issues": {}}},
    )
    pass_io.write_json(
        pass_io.working_path(pd), {"actions": [], "survey_errors": 0}
    )
    listed = {
        "mikolaj92/Temida": [
            {"number": 4972, "labels": ["enhancement"]},
            {"number": 4973, "labels": ["bug"]},
            {"number": 4969, "labels": ["work:ready"]},
        ],
        "mikolaj92/Fala": [{"number": 176, "labels": ["oil"]}],
    }

    def fake_fetch(selected, **kwargs):
        repo = selected["repo"]
        return {
            **selected,
            "ok": True,
            "route": "listed",
            "issues": listed[repo],
            "listed": {"ok": True, "issues": listed[repo]},
        }

    monkeypatch.setattr("lokay.proc.list_inbox_repo_issues.fetch", fake_fetch)
    prepared = {
        "ok": True,
        "repos": ["mikolaj92/Temida", "mikolaj92/Fala"],
        "mini_repo": "mikolaj92/lokay",
        "skipped_repos": [],
        "active_repos": ["mikolaj92/Temida", "mikolaj92/Fala"],
        "scoped": False,
        "stuck": {"issues": {}},
        "recent_empty": False,
    }
    out = inbox_survey_catalog.run(
        prepared, pass_dir=str(pd), config_path=None, live=False
    )
    assert out["remaining_inbox"] == 4
    working = pass_io.read_json(pass_io.working_path(pd))
    assert working["remaining_inbox"] == 4
    assert [x["number"] for x in working["inbox_issues_by_repo"]["mikolaj92/Temida"]] == [
        4972,
        4973,
        4969,
    ]
    assert [x["number"] for x in working["inbox_issues_by_repo"]["mikolaj92/Fala"]] == [
        176
    ]
