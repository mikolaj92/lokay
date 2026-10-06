import pytest

from lokay.organ.pr_outcome import handle_pr_outcome
from lokay.proc import run_pr_triage_subflow
from lokay.proc.select_pr_triage_verdict import select
from lokay.proc.walk_pr_leftover import consumes


def test_pending_checks_survive_skipped_repair_branch():
    result = handle_pr_outcome(
        "summarize_pr_triage", {},
        {
            "publish_pr_review": {"decision": {"verdict": "not_applicable"}},
            "select_pr_triage_outcome": {"route": "wait", "waiting": True, "reason": "checks_pending"},
            "pr_repair_verdict": {"reason": "condition_not_met", "when": {"equals": "repair"}},
        }, {},
    )
    assert result["ok"] is True
    assert result["result"]["waiting"] is True
    assert result["result"]["reason"] == "checks_pending"
    assert result["result"]["repairable"] is False


@pytest.mark.parametrize("failure", [{"ok": False}, {"ok": True, "run_status": "failed"}])
def test_failed_child_does_not_consume_review_queue_head(monkeypatch, failure):
    monkeypatch.setattr(run_pr_triage_subflow, "run_path", lambda **kwargs: {
        **failure,
        "terminal": {"summarize_pr_triage": {"ok": False, "error": "unrouted review verdict"}},
    })
    target = {"route": "pr", "repo": "owner/product", "pr": 219, "branch": "ai/fix/161", "head_sha": "7" * 40}
    child = run_pr_triage_subflow.run(target, config_path=None, live=False)
    verdict = select(target, child, {"route": "review"})
    assert child["triage"]["waiting"] is True
    assert child["triage"]["merged"] is False
    assert child["triage"]["repairable"] is False
    assert consumes(verdict) is False
