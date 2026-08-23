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
