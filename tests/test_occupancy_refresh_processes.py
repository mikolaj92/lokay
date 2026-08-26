"""Contracts for minimal occupancy-refresh processes."""

import inspect

from lokay.proc.reduce_occupancy_facts import reduce_state as reduce_facts
from lokay.proc.reduce_occupancy_refresh import reduce_state


def test_refresh_occupancy_subflow_uses_handful_of_ticks():
    from lokay.proc.refresh_occupancy_subflow import run

    source = inspect.getsource(run)
    assert "max_ticks=16" in source
    assert "max_ticks=512" not in source


def test_catalog_fail_closed_when_prepare_failed():
    from lokay.proc.occupancy_catalog import run

    out = run(
        {"ok": False, "error": "occupancy inputs exceed authored slots"},
        pass_dir="unused",
        config_path=None,
        live=True,
    )
    assert out["ok"] is False and "exceed authored slots" in out["error"]


def test_catalog_overflow_is_fail_closed():
    from lokay.proc.occupancy_catalog import SLOTS, run

    out = run(
        {"ok": True, "receipts": [{}] * (SLOTS + 1), "repos": []},
        pass_dir="unused",
        config_path=None,
        live=True,
    )
    assert out["ok"] is False and "exceed authored slots" in out["error"]


def test_catalog_clears_closed_live_receipt(tmp_path, monkeypatch):
    from lokay.passkit import io as pass_io
    from lokay.proc.occupancy_catalog import run

    killed = []
    cleared = []
    monkeypatch.setattr(
        "lokay.proc.inspect_live_receipt_issue.inspect",
        lambda selected, **_k: {
            "ok": True,
            "route": "closed",
            "repo": "a/one",
            "issue": 2,
            "receipt": selected["receipt"],
        },
    )
    monkeypatch.setattr(
        "lokay.proc.terminate_closed_issue_worker.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )
    monkeypatch.setattr(
        "lokay.proc.clear_closed_issue_receipt.clear_issue_to_pr_receipt",
        lambda row: not cleared.append(row),
    )
    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(pass_io.begin_path(path), {"repos": ["a/one"]})
    pass_io.write_json(
        pass_io.working_path(path),
        {
            "actions": [],
            "prs_by_repo": {},
            "pr_survey_failed": [],
            "ready_by_repo": {},
        },
    )
    out = run(
        {
            "ok": True,
            "merged": [],
            "receipts": [{"repo": "a/one", "issue": 2, "pid": 9}],
            "repos": ["a/one"],
        },
        pass_dir=str(path),
        config_path=None,
        live=True,
    )
    assert out["ok"] is True
    assert out["state"]["occupied_repos"] == []
    assert out["state"]["cleared_issue_to_pr_receipts"] == [
        {"repo": "a/one", "issue": 2}
    ]
    assert killed == [(9, __import__("signal").SIGTERM)]
    assert cleared == [{"repo": "a/one", "issue": 2, "pid": 9}]


def test_catalog_empty_skips_physical_effects(tmp_path, monkeypatch):
    from lokay.passkit import io as pass_io
    from lokay.proc.occupancy_catalog import run

    called = []

    def fail(*_a, **_k):
        called.append(True)
        raise AssertionError("physical effect must not run")

    monkeypatch.setattr("lokay.proc.inspect_live_receipt_issue.inspect", fail)
    monkeypatch.setattr("lokay.proc.list_occupancy_pull_requests.fetch", fail)
    path = tmp_path / "pass"
    path.mkdir()
    pass_io.write_json(pass_io.begin_path(path), {"repos": []})
    pass_io.write_json(
        pass_io.working_path(path),
        {"actions": [], "prs_by_repo": {}, "pr_survey_failed": []},
    )
    out = run(
        {"ok": True, "merged": [], "receipts": [], "repos": []},
        pass_dir=str(path),
        config_path=None,
        live=True,
    )
    assert out["ok"] is True and not called


def test_closed_receipt_is_cleared_not_occupied():
    out = reduce_facts(
        prepared={"merged": [], "receipt_state_unknown": False},
        merged_clear={"cleared": []},
        results=[
            {
                "route": "closed",
                "repo": "a/one",
                "receipt": {"repo": "a/one", "issue": 2},
                "cleared": True,
            }
        ],
    )
    assert out["occupied"] == [] and out["cleared"] == [{"repo": "a/one", "issue": 2}]


def test_failed_pr_probe_keeps_previous_snapshot():
    previous = {"number": 3, "labels": ["ai:generated"]}
    out = reduce_state(
        facts={"merged": [], "live_repos": [], "occupied": [], "cleared": []},
        results=[
            {
                "route": "failed",
                "repo": "a/one",
                "previous": [previous],
                "listed": {"ok": False, "error": "429"},
            }
        ],
        working={
            "actions": [],
            "prs_by_repo": {"a/one": [previous]},
            "pr_survey_failed": [],
            "inbox_survey_failed": [],
            "ready_survey_failed": [],
        },
    )["state"]
    assert out["prs_by_repo"]["a/one"] == [previous] and out["pr_survey_failed"] == [
        "a/one"
    ]


def test_record_repo_ignores_skipped_optional_listing():
    from lokay.proc.record_repo_pr_refresh import record

    out = record(
        {"route": "repo"},
        {"ok": True, "route": "no_ready", "repo": "a/one"},
        {"ok": False, "reason": "condition_not_met"},
    )
    assert out["route"] == "no_ready"
