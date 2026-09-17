"""Small Unix processes at the PR-review entropy boundary."""

from types import SimpleNamespace

from lokay.proc import publish_pr_review


def _cfg():
    return SimpleNamespace(max_request_changes_per_pr=2)


def test_publish_cached_result_preserves_merge_policy_without_mutating(monkeypatch):
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_: (_ for _ in ()).throw(AssertionError("no mutation")))
    out=publish_pr_review.publish(cfg=_cfg(),repo="a/b",pr=7,evidence={"head_sha":"a"*40},selected={"route":"cached","decision":{"verdict":"approve"},"merge_ok":True},live=True)
    assert out["decision"]["verdict"] == "approve"
    assert out["merge_ok"] is True
    assert out["applied"] is False
    assert out["execution"] == {"source":"cached"}


def test_cached_request_changes_preserves_escalation_after_restart(monkeypatch):
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_: (_ for _ in ()).throw(AssertionError("no mutation")))
    out=publish_pr_review.publish(
        cfg=SimpleNamespace(max_request_changes_per_pr=2), repo="a/b", pr=7,
        evidence={"head_sha":"a"*40},
        selected={
            "route":"cached", "merge_ok":False, "request_changes_count":3,
            "decision":{
                "verdict":"request_changes", "findings":[{"path":"src/a.py"}],
                "reviewed_head_sha":"a"*40, "task_identity_sha256":"b"*64,
                "review_result_sha256":"c"*64,
                "task":{"repo":"a/b", "type":"Issue", "state":"OPEN"},
            },
        }, live=True,
    )
    assert out["escalated"] is True
    assert out["request_changes_count"] == 3
    assert out["merge_ok"] is False


def test_exhausted_invalid_review_publishes_terminal_not_approval(monkeypatch):
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_:True)
    monkeypatch.setattr(publish_pr_review,"runner",lambda *_:object())
    applied=[]
    monkeypatch.setattr(publish_pr_review,"publish_fail_closed",lambda *_args,**_kwargs:applied.append(_kwargs) or True)
    out=publish_pr_review.publish(cfg=_cfg(),repo="a/b",pr=7,evidence={"head_sha":"a"*40},selected={"route":"fail_closed","reason":"invalid_review_json_exhausted","validation_error":"bad"},live=True)
    assert out["decision"] == {"verdict":"fail_closed"}
    assert out["merge_ok"] is False and applied
    assert applied[0]["head_sha"] == "a" * 40


def test_fail_closed_comment_binds_head_sha_so_the_same_pr_is_not_reviewed_again(monkeypatch):
    from lokay.pr_review import parse_review_markers
    from lokay.pr_review_io import publish_fail_closed

    posted: list[str] = []
    monkeypatch.setattr(
        "lokay.pr_review_io.publish_review",
        lambda _runner, _repo, _pr, body, _labels, live: posted.append(body),
    )
    head = "f" * 40
    applied = publish_fail_closed(
        object(), "a/b", 39, ValueError("ocr_exited_unsuccessfully"),
        mutate=True, head_sha=head,
    )
    markers = parse_review_markers(posted)
    assert applied is True
    assert markers[-1]["head_sha"] == head
    assert markers[-1]["verdict"] == "fail_closed"
    assert markers[-1]["merge_ok"] is False


def test_verify_supplement_rejects_changed_sha(monkeypatch):
    from lokay.proc import verify_review_evidence_sha
    monkeypatch.setattr(verify_review_evidence_sha,"runner",lambda:object())
    monkeypatch.setattr(verify_review_evidence_sha,"gh_json",lambda *_args,**_kwargs:{"headRefOid":"new"})
    out=verify_review_evidence_sha.verify(repo="a/b",pr=7,expected_sha="old",live=True)
    assert out["ok"] is True and out["route"] == "fail_closed"
    assert out["expected_sha"] == "old" and out["actual_sha"] == "new"


def test_missing_selected_evidence_routes_fail_closed_without_agent(monkeypatch):
    from lokay.organ.review_boundary import handle_review_boundary
    ctx={"repo":"a/b","pr_number":7,"branch":"b","live":True}
    monkeypatch.setattr(
        "lokay.proc.collect_review_changed_files.collect",
        lambda **_k: {"ok": True, "collected": False, "reason": "unavailable"},
    )
    up={
        "collect_pr_review_evidence":{"evidence":{"head_sha":"abc"}},
        "select_pr_review":{"ok":True,"route":"evidence","evidence_kind":"changed_files"},
    }
    out=handle_review_boundary("review_evidence_catalog",{},up,ctx)
    assert out["ok"] is True and out["route"] == "fail_closed"
    assert out["reason"] == "unavailable"
