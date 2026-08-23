"""Contracts for minimal occupancy-refresh processes."""

from lokay.proc.reduce_occupancy_facts import reduce_state as reduce_facts
from lokay.proc.reduce_occupancy_refresh import reduce_state


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
