"""PR review domain outcomes stay separate from execution/cache metadata."""

from lokay.proc.review_repair_gate import route_review_repair
from lokay.proc.review_terminal import terminal_review


def test_request_changes_routes_to_repair_even_when_review_was_reused():
    result = route_review_repair({
        "skipped": True, "reason": "already_reviewed_head",
        "decision": {"verdict": "request_changes", "secrets": False},
    })
    assert result == {"ok": True, "route": "repair", "reason": "review_requested_changes"}


def test_request_changes_cap_routes_to_terminal_human():
    result = route_review_repair({
        "escalated": True,
        "decision": {"verdict": "request_changes", "secrets": False},
    })
    assert result["route"] == "needs_human"


def test_secret_request_changes_routes_to_terminal_human():
    result = route_review_repair({
        "decision": {"verdict": "request_changes", "secrets": True},
    })
    assert result["route"] == "needs_human"


def test_manual_terminal_is_a_domain_result():
    result = terminal_review(verdict="needs_human", reason="review_needs_human")
    assert result["terminal"] is True
    assert result["verdict"] == "needs_human"
    assert result["needs_review"] is True


def test_pr_outcome_handler_routes_reused_request_changes(monkeypatch):
    from lokay.organ.pr_outcome import handle_pr_outcome
    out = handle_pr_outcome(
        "review_repair_gate", {},
        {"publish_pr_review": {"execution": {"source": "cache"}, "decision": {"verdict": "request_changes"}}},
        {"repo": "a/b", "pr_number": 7, "branch": "ai/fix/7-x", "live": []},
    )
    assert out["route"] == "repair"


def test_pr_repair_subflow_forwards_review(monkeypatch):
    from lokay.proc import pr_repair_subflow as module
    calls = []
    monkeypatch.setattr(module, "compose_pr_repair", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    review = {"decision": {"verdict": "request_changes"}, "head_sha": "abc"}
    out = module.run_pr_repair_subflow(
        config_path="cfg", repo="a/b", pr=7, branch="ai/fix/7-x", review=review, live=True,
    )
    assert out["ok"] is True
    assert calls == [{
        "config_path": "cfg", "repo": "a/b", "pr_number": 7,
        "branch": "ai/fix/7-x", "review": review, "live": True,
    }]
