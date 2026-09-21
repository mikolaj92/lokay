"""pr_triage department: review + merge. repair is a verdict, not a child."""

import tomllib
from pathlib import Path

import pytest

from lokay.proc.select_pr_repair_department import select as select_repair
from lokay.proc.select_pr_triage_verdict import classify, select
from lokay.proc.summarize_pr_triage_department import summarize


def _path(path_id: str) -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == path_id)


def test_verdict_is_merge_feedback_or_repair() -> None:
    picked = {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}
    assert select(picked, {"triage": {"merged": True}}, {"route": "review"})["verdict"] == "merge"
    assert select(picked, {"triage": {"repairable": True, "reason": "red_ci"}}, {"route": "review"})[
        "verdict"
    ] == "repair"
    assert select(picked, {"triage": {"waiting": True}}, {"route": "review"})["verdict"] == "feedback"
    assert select(picked, {"triage": {}}, {"route": "review"})["verdict"] == "feedback"
    assert "run_pr_repair" not in select(picked, {"triage": {"repairable": True}}, {"route": "review"})


def test_selected_pr_requires_explicit_reconciliation_review_route():
    picked = {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}
    out = select(picked, {"triage": {"merged": True}})
    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_push_recovery_route_invalid"
    assert out["merged"] is False
    assert out["repairable"] is False


def test_empty_pr_queue_does_not_require_reconciliation():
    picked = {"route": "none", "reason": "no_open_pr"}
    out = select(picked, {}, {"route": "no_pr"})
    assert out["route"] == "skip"
    assert out["reason"] == "no_open_pr"
    receipt = summarize(picked, {}, out, {"route": "no_pr"})
    assert receipt["route"] == "none"
    assert receipt["recovery_route"] == "no_pr"
    assert receipt["recovery_reason"] == ""


def test_recovery_outcome_suppresses_review_and_merge():
    picked = {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}
    for recovery, expected_route, reason in (
        ({"route": "review"}, "completed", ""),
        ({"route": "recovered", "recovered": [{"repo": "o/r", "pr": 9}]}, "skip", "repair_push_recovered"),
        ({"route": "fail_closed", "reason": "repair_push_remote_identity_mismatch"}, "fail_closed", "repair_push_remote_identity_mismatch"),
    ):
        out = select(picked, {"triage": {"merged": True}}, recovery)
        if expected_route == "completed":
            assert out["verdict"] == "merge"
        else:
            assert out["route"] == expected_route
            assert out["reason"] == reason
            assert out["triage"]["recovery_route"] == recovery["route"]
            assert out["merged"] is False
            assert out["repairable"] is False
            assert out["waiting"] is True
            assert out["repo"] == "o/r" and out["pr"] == 9


def test_classify_does_not_start_repair() -> None:
    facts = classify({"triage": {"repairable": True, "reason": "request_changes"}})
    assert facts["repairable"] is True
    assert "started" not in facts


def test_receipt_never_starts_repair() -> None:
    out = summarize(
        {"route": "pr", "pr": 9},
        {"route": "completed", "triage": {"repairable": True}},
        {"verdict": "repair", "repairable": True, "pr": 9},
        {"route": "review"},
    )
    assert out["repair_started"] is False
    assert out["verdict"] == "repair"
    assert out["department"] == "pr_triage"
    assert out["result"]["verdict"] == "repair"
    assert out["result"]["repair_started"] is False
    assert "run_pr_repair" not in out["result"]


def test_select_pr_sieve_walks_last_pass_leftover(monkeypatch):
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department

    seen = []

    def fake_select(listed, last=None):
        seen.append((listed, last))
        return {"ok": True, "route": "pr", "pr": 30}

    monkeypatch.setattr("lokay.proc.select_next_pr.select", fake_select)
    last = {
        "leftover_prs": [{"repo": "mikolaj92/VibeFront", "pr": 30, "head_sha": "abc"}],
        "skipped_pr": 39,
        "skipped_head_sha": "f654e881",
    }
    out = handle_pr_triage_department(
        "select_pr_sieve",
        {"last": last},
        {"list_pr_sieve": {"ok": True, "prs": [{"repo": "o/r", "pr": 39}]}},
        {},
    )
    assert out["pr"] == 30
    assert seen == [
        ({"ok": True, "prs": [{"repo": "o/r", "pr": 39}]}, last),
    ]


def test_reconcile_boundary_scans_without_candidate_but_does_not_open_review(monkeypatch):
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department

    seen = []
    monkeypatch.setattr(
        "lokay.proc.reconcile_pr_repair_push.reconcile_pending",
        lambda **kwargs: seen.append(kwargs) or {"ok": True, "route": "no_pr", "recovered": []},
    )
    out = handle_pr_triage_department(
        "reconcile_pr_repair_push", {"config_path": "config.yaml", "live": True},
        {"select_pr_sieve": {"route": "none", "reason": "no_open_pr"}}, {},
    )
    assert out["route"] == "no_pr"
    assert out["recovered"] == []
    assert seen == [{"config_path": "config.yaml", "live": True, "selection": {
        "route": "none", "reason": "no_open_pr",
    }}]


def test_child_boundary_wires_reconciliation_into_verdict_and_summary():
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department

    recovery = {
        "ok": True, "route": "fail_closed",
        "reason": "repair_push_remote_identity_mismatch",
        "recovered": [{"repo": "o/r", "pr": 9}],
    }
    upstream = {
        "select_pr_sieve": {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        "run_pr_sieve": {"triage": {"merged": True, "repairable": True}},
        "reconcile_pr_repair_push": recovery,
    }
    verdict = handle_pr_triage_department("select_pr_triage_verdict", {}, upstream, {})
    summary = handle_pr_triage_department(
        "summarize_pr_triage_department", {},
        {**upstream, "select_pr_triage_verdict": verdict}, {},
    )

    assert verdict["route"] == "fail_closed"
    assert verdict["reason"] == recovery["reason"]
    assert verdict["merged"] is False and verdict["repairable"] is False
    assert summary["route"] == "fail_closed"
    assert summary["recovery_route"] == "fail_closed"
    assert summary["recovery_reason"] == recovery["reason"]
    assert summary["triage"]["merged"] is False
    assert summary["triage"]["repairable"] is False


def test_run_pr_sieve_lifts_pr_identity_from_reconciliation_handoff(monkeypatch):
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department

    seen: list[tuple[dict, dict]] = []
    monkeypatch.setattr(
        "lokay.proc.run_pr_triage_subflow.run",
        lambda target, **kwargs: seen.append((target, kwargs)) or {"ok": True},
    )

    out = handle_pr_triage_department(
        "run_pr_sieve",
        {"config_path": "config.yaml", "live": True},
        {
            "reconcile_pr_repair_push": {
                "ok": True,
                "route": "review",
                "repo": "o/r",
                "pr": 9,
                "branch": "ai/fix/9-x",
            },
        },
        {},
    )

    assert out == {"ok": True}
    assert seen == [
        (
            {"ok": True, "route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
            {"config_path": "config.yaml", "live": True},
        ),
    ]


def test_selected_pr_with_empty_or_failed_listing_cannot_enter_review(monkeypatch):
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department

    routes = []
    monkeypatch.setattr(
        "lokay.proc.reconcile_pr_repair_push.reconcile_pending",
        lambda **kwargs: routes.append(kwargs["selection"]) or {
            "ok": True, "route": "review" if kwargs["selection"].get("route") == "pr" else "no_pr",
            "recovered": [],
        },
    )
    for picked in (
        {"route": "none", "reason": "no_open_pr"},
        {"route": "none", "reason": "list_failed", "ok": False},
    ):
        reconciled = handle_pr_triage_department(
            "reconcile_pr_repair_push", {}, {"select_pr_sieve": picked}, {},
        )
        verdict = select(picked, {"triage": {"merged": True}}, reconciled)
        assert reconciled["route"] == "no_pr"
        assert verdict["route"] == "skip"
        assert verdict["verdict"] == "none"
    assert routes == [
        {"route": "none", "reason": "no_open_pr"},
        {"route": "none", "reason": "list_failed", "ok": False},
    ]


def test_recovery_result_is_exposed_and_blocks_repair():
    out = summarize(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        {"route": "completed", "triage": {"merged": True}},
        {"route": "completed", "verdict": "merge", "merged": True,
         "repo": "o/r", "pr": 9},
        {"route": "fail_closed", "reason": "repair_push_remote_identity_mismatch",
         "recovered": [{"repo": "o/r", "pr": 9, "head_sha": "b" * 40,
                        "intent_sha256": "c" * 64}],
         "repair_push_intent_sha256": "c" * 64},
    )
    assert out["route"] == "fail_closed"
    assert out["verdict"] == "feedback"
    assert out["repair_started"] is False
    assert out["triage"]["repairable"] is False
    assert out["triage"]["merged"] is False
    assert out["triage"]["recovery_route"] == "fail_closed"
    assert out["recovery_reason"] == "repair_push_remote_identity_mismatch"
    assert out["recovered_pushes"] == [{"repo": "o/r", "pr": 9, "head_sha": "b" * 40,
                                        "intent_sha256": "c" * 64}]
    assert out["repair_push_intent_sha256"] == "c" * 64
    assert out["triage"]["repair_push_intent_sha256"] == "c" * 64
    assert out["result"] == {key: value for key, value in out.items() if key != "result"}


def test_missing_repair_kind_fails_closed_instead_of_defaulting_to_ci(tmp_path) -> None:
    out = select_repair(
        {
            "triage": {"repairable": True, "reason": "red_ci",
                       "review": {"verdict": "request_changes"}},
            "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x",
        },
        enabled=True, triage_ran=True, state_dir=tmp_path,
    )
    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_kind_invalid"


def test_ci_repair_route_does_not_require_review_handoff(tmp_path) -> None:
    out = select_repair(
        {
            "triage": {"repairable": True, "reason": "red_ci", "repair_kind": "ci",
                       "review": {"verdict": "request_changes"}},
            "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x", "head_sha": "a" * 40,
        },
        enabled=True, triage_ran=True, state_dir=tmp_path,
    )
    assert out["route"] == "repair"
    assert out["repair_kind"] == "ci"
    assert out["task"] == {} and out["findings"] == []


def test_incomplete_review_repair_fails_closed(tmp_path) -> None:
    out = select_repair(
        {
            "triage": {"repairable": True, "reason": "review_requested_changes", "repair_kind": "review",
                       "review": {"verdict": "request_changes"}},
            "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x",
        },
        enabled=True, triage_ran=True, state_dir=tmp_path,
    )
    assert out["route"] == "fail_closed"
    assert out["reason"] == "review_repair_handoff_incomplete"


def test_parent_repair_reads_the_verdict(tmp_path) -> None:
    out = select_repair(
        {
            "triage": {
                "repairable": True,
                "reason": "red_ci",
                "repair_kind": "ci",
                "review": {"verdict": "not_applicable"},
            },
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
            "head_sha": "a" * 40,
        },
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
    )
    assert out["route"] == "repair"
    assert out["repair_kind"] == "ci"
    assert out["review"] == {"verdict": "not_applicable"}
    assert select_repair({}, enabled=True, triage_ran=True, state_dir=tmp_path)["reason"] == "no_triage_verdict"


def test_parent_repair_reads_normalized_sieve_envelope(tmp_path) -> None:
    lifted = {
        "ok": True,
        "engine": "fala",
        "path_id": "pr_triage_department",
        "verdict": "repair",
        "triage": {"repairable": True, "reason": "red_ci", "repair_kind": "ci"},
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        "head_sha": "a" * 40,
        "repair_started": False,
    }
    out = select_repair(lifted, enabled=True, triage_ran=True, state_dir=tmp_path)
    assert out["route"] == "repair"
    assert out["repo"] == "o/r" and out["pr"] == 9
    assert out["branch"] == "ai/fix/9-x"


def test_disabled_repair_does_not_touch_sieve_feedback(tmp_path) -> None:
    receipt = summarize(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        {"route": "completed", "triage": {"repairable": True, "reason": "red_ci"}},
        {"verdict": "repair", "repairable": True, "repo": "o/r", "pr": 9},
        {"route": "review"},
    )
    out = select_repair(receipt, enabled=False, triage_ran=True, state_dir=tmp_path)
    assert out["route"] == "skip"
    assert out["reason"] == "pr_repair_disabled"
    assert receipt["repair_started"] is False


@pytest.mark.parametrize("reason,waiting,keep", [
    ("merge_not_confirmed", True, True),
    ("merge_head_unverified", True, True),
    ("future_wait_reason", True, True),
    ("review_fail_closed", False, False),
    ("ocr_contract_rejected: review has warnings", False, False),
])
def test_final_queue_stamp_preserves_child_wait_without_verdict_copy(reason, waiting, keep):
    from lokay.proc.walk_pr_leftover import classify_occupancy

    row = {"repo": "owner/repo", "pr": 7, "branch": "ai/fix/7", "head_sha": "b" * 40}
    receipt = summarize(
        {**row, "route": "pr", "leftover_prs": []},
        {"triage": {"waiting": waiting, "reason": reason}},
        {"route": "completed", "verdict": "feedback", "reason": reason},
        {"route": "review"},
    )
    assert receipt["waiting"] is waiting
    assert receipt["result"]["waiting"] is waiting
    assert classify_occupancy(receipt)["keep"] is keep
    assert receipt["leftover_prs"] == ([row] if keep else [])
    assert ("skipped_head_sha" not in receipt) is keep


def test_department_graph_has_no_repair_child() -> None:
    ids = [str(node["id"]) for node in _path("pr_triage_department")["effectors"]]
    assert ids == [
        "list_pr_sieve",
        "select_pr_sieve",
        "reconcile_pr_repair_push",
        "recover_repair_pre_attempt",
        "recover_repair_remote_unchanged",
        "recover_repair_confirmed_target",
        "recover_repair_closed_merged",
        "recover_repair_unavailable",
        "run_pr_sieve",
        "select_pr_triage_verdict",
        "summarize_pr_triage_department",
    ]
    assert "run_pr_repair_subflow" not in ids
    assert "select_pr_repair" not in ids
    assert "run_pr_triage_subflow" not in ids
    by_id = {node["id"]: node for node in _path("pr_triage_department")["effectors"]}
    assert "when" not in by_id["reconcile_pr_repair_push"]
    assert by_id["run_pr_sieve"]["when"] == {
        "upstream": "reconcile_pr_repair_push",
        "path": "route",
        "equals": "review",
    }
