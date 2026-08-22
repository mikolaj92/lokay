"""Structured PR review parse + policy and repository boundary."""

import json

import pytest

from lokay.proc import pr_review as pr_review_proc
from lokay.pr_review import (
    PrReviewError,
    build_review_comment_body,
    count_request_changes_reviews,
    decide_review_merge,
    find_review_for_head,
    format_review_marker,
    labels_for_review,
    parse_review_markers,
    parse_review_output,
    should_escalate_request_changes,
    should_merge,
    should_repair,
    review_prompt,
)




def test_lokay_repo_still_loads_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = type("Cfg", (), {"mode": "live", "executor_enabled": True})()
    sentinel_runner = object()
    calls: list[tuple[object, str, int, bool]] = []

    monkeypatch.setattr(pr_review_proc, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(pr_review_proc, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(pr_review_proc, "agent_execute_allowed", lambda *_args, **_kwargs: True)

    def load_evidence(
        evidence_runner: object, repo: str, pr: int, *, live: bool, **_kwargs: object
    ) -> dict[str, object]:
        calls.append((evidence_runner, repo, pr, live))
        return {
            "title": "title", "body": "", "head": "branch", "head_sha": "sha",
            "comments": [], "diff": "diff", "checks_text": "checks",
        }

    monkeypatch.setattr(pr_review_proc, "load_pr_evidence", load_evidence)
    monkeypatch.setattr(
        pr_review_proc,
        "run_agent",
        lambda *_args, **_kwargs: {"status": "planned"},
    )
    monkeypatch.setattr(pr_review_proc, "review_worktree", lambda *_args: tmp_path)

    assert pr_review_proc.main(["--repo", "mikolaj92/lokay", "--pr", "490"]) == 0
    assert calls == [(sentinel_runner, "mikolaj92/lokay", 490, False)]
    assert json.loads(capsys.readouterr().out)["planned"] is True


def test_review_evidence_failure_returns_probe_failed_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = type("Cfg", (), {"mode": "live", "executor_enabled": True})()
    monkeypatch.setattr(pr_review_proc, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(pr_review_proc, "runner", lambda: object())
    monkeypatch.setattr(pr_review_proc, "agent_execute_allowed", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        pr_review_proc,
        "load_pr_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("diff unavailable")),
    )
    monkeypatch.setattr(
        pr_review_proc,
        "run_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("review must not run without evidence")
        ),
    )

    assert pr_review_proc.main(
        ["--repo", "mikolaj92/lokay", "--pr", "490", "--live"]
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["probe_failed"] is True
    assert payload["merge_ok"] is False
    assert "diff unavailable" in payload["error"]


def test_parse_plain_json():
    d = parse_review_output(
        '{"verdict":"approve","risk":"low","scope_ok":true,"secrets":false,'
        '"tests_adequate":true,"blocking":[],"nits":[],"summary":"ok"}'
    )
    assert d.verdict == "approve"
    assert should_merge(d) is True


def test_parse_fenced_json():
    text = """Here is my review:
```json
{"verdict": "request_changes", "risk": "medium", "scope_ok": false,
 "secrets": false, "tests_adequate": false,
 "blocking": ["missing tests"], "nits": ["typo"], "summary": "needs work"}
```
"""
    d = parse_review_output(text)
    assert d.verdict == "request_changes"
    assert should_merge(d) is False
    assert "missing tests" in d.blocking


def test_parse_fail_closed_empty():
    with pytest.raises(PrReviewError):
        parse_review_output("")


def test_parse_fail_closed_bad_verdict():
    with pytest.raises(PrReviewError):
        parse_review_output('{"verdict":"lgtm","summary":"nope"}')


def test_should_merge_rejects_secrets():
    d = parse_review_output(
        '{"verdict":"approve","secrets":true,"summary":"has key"}'
    )
    assert should_merge(d) is False


def test_should_merge_rejects_blocking():
    d = parse_review_output(
        '{"verdict":"approve","blocking":["x"],"summary":"x"}'
    )
    assert should_merge(d) is False


def test_needs_human():
    d = parse_review_output(
        '{"verdict":"needs_human","risk":"high","summary":"policy"}'
    )
    assert d.verdict == "needs_human"
    assert should_merge(d) is False


def test_request_changes_is_repairable_without_secrets():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":false,"blocking":["fix it"]}'
    )
    assert should_repair(d) is True
    assert should_merge(d) is False


def test_request_changes_with_secrets_is_not_repairable():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":true,"blocking":["key"]}'
    )
    assert should_repair(d) is False


@pytest.mark.parametrize(
    "field", ["scope_ok", "tests_adequate"]
)
def test_approve_rejects_false_safety_field(field):
    d = parse_review_output(f'{{"verdict":"approve","{field}":false}}')
    assert should_merge(d) is False


def test_boolean_strings_fail_closed():
    with pytest.raises(PrReviewError):
        parse_review_output('{"verdict":"approve","secrets":"false"}')


def test_review_prompt_sets_collector_execution_boundary():
    prompt = review_prompt(
        repo="a/b",
        pr_number=7,
        title="collector patch",
        body="",
        head_ref="ai/fix/7-collector",
        diff_text="diff --git a/x.py b/x.py\n",
        checks_text="",
    )
    assert "Collector boundary" in prompt
    assert "must not use Pi or the mill to populate data" in prompt
    assert "wait for collection to finish" in prompt


def _prompt_with_plan_in_diff() -> str:
    diff = (
        "diff --git a/.lokay/approach.md b/.lokay/approach.md\n"
        "--- /dev/null\n+++ b/.lokay/approach.md\n"
        "@@ -0,0 +1,4 @@\n"
        "+# Approach plan\n"
        "+## Goal\n"
        "+SECRET_PLAN_GOAL_SHIP_THE_ATOM\n"
        "+## Files\n"
        "+src/lokay/pr_review.py\n"
        "diff --git a/src/lokay/pr_review.py b/src/lokay/pr_review.py\n"
        "--- a/src/lokay/pr_review.py\n+++ b/src/lokay/pr_review.py\n"
        "@@ -1 +1,2 @@\n"
        " # review\n"
        "+REAL_CODE_HUNK\n"
    )
    return review_prompt(
        repo="owner/repo",
        pr_number=42,
        title="blind review ticket",
        body="Ticket body: fix the review atom.",
        head_ref="ai/fix/42-blind",
        diff_text=diff,
        checks_text="pytest tests/test_pr_review.py PASSED",
    )


def test_review_prompt_is_blind_to_approach_plan():
    """Reviewer sees ticket + code diff + tests; never the builder plan."""
    text = _prompt_with_plan_in_diff()
    lowered = text.lower()
    assert "blind review ticket" in text
    assert "Ticket body: fix the review atom." in text
    assert "REAL_CODE_HUNK" in text
    assert "pytest tests/test_pr_review.py PASSED" in text
    assert "SECRET_PLAN_GOAL_SHIP_THE_ATOM" not in text
    assert "approach.md" not in lowered
    assert "approach excerpt" not in lowered
    assert "approach evidence" not in lowered
    assert "approach plan" not in lowered
    assert "porównaj" not in lowered
    assert "compare the implementation" not in lowered
    assert "compare the diff to" not in lowered
    assert "compare" not in lowered or "plan" not in lowered
    assert "soft signal" not in lowered
    assert "porównaj do planu" not in lowered


def test_review_marker_roundtrip_and_head_lookup():
    body = build_review_comment_body(
        parse_review_output(
            '{"verdict":"request_changes","secrets":false,"blocking":["x"],'
            '"summary":"fix"}'
        ),
        head_sha="abcDEF12",
        merge_ok=False,
    )
    markers = parse_review_markers([body])
    assert len(markers) == 1
    assert markers[0]["head_sha"] == "abcdef12"
    assert markers[0]["verdict"] == "request_changes"
    assert find_review_for_head(markers, "ABCDEF12")["merge_ok"] is False


def test_request_changes_escalation_cap():
    assert should_escalate_request_changes(0, max_request_changes=2) is False
    assert should_escalate_request_changes(1, max_request_changes=2) is True
    markers = parse_review_markers(
        [
            format_review_marker(head_sha="a" * 40, verdict="request_changes", merge_ok=False),
            format_review_marker(head_sha="b" * 40, verdict="approve", merge_ok=True),
            format_review_marker(head_sha="c" * 40, verdict="request_changes", merge_ok=False),
        ]
    )
    assert count_request_changes_reviews(markers) == 2
    assert should_escalate_request_changes(2, max_request_changes=2) is True


def test_labels_and_merge_decision_helpers():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":false,"blocking":["x"]}'
    )
    assert labels_for_review(d, escalated=False) == ["ai:request-changes"]
    assert labels_for_review(d, escalated=True) == ["ai:needs-review"]
    merge_ok, escalated = decide_review_merge(d, 1, max_request_changes=2)
    assert merge_ok is False
    assert escalated is True
