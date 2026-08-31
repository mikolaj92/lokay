"""Small Unix processes at the PR-review entropy boundary."""

from types import SimpleNamespace

from lokay.proc import (
    _pr_review_agent_runtime, publish_pr_review, run_evidence_review_agent,
    run_pr_review_agent, run_pr_review_retry_agent,
)


def _cfg():
    return SimpleNamespace(max_request_changes_per_pr=2)


def test_retry_agent_receives_validator_feedback(monkeypatch, tmp_path):
    cfg=SimpleNamespace(executor_enabled=True)
    monkeypatch.setattr("lokay.config.load_config",lambda _:cfg)
    monkeypatch.setattr(_pr_review_agent_runtime,"agent_execute_allowed",lambda *_args,**_kwargs:True)
    monkeypatch.setattr(_pr_review_agent_runtime,"review_worktree",lambda *_args:tmp_path)
    prompts=[]
    monkeypatch.setattr(_pr_review_agent_runtime,"run_agent",lambda *_args,**kwargs:prompts.append(kwargs["prompt"]) or {"status":"completed","stdout_tail":"{}"})
    evidence={"title":"x","body":"","head":"b","head_sha":"abc","diff":"d","checks_text":""}
    out=run_pr_review_retry_agent.run(config_path=None,repo="a/b",pr=7,evidence=evidence,live=True,feedback={"validation_error":"verdict missing","agent_stdout_tail":"{}"})
    assert out["ok"] is True
    assert "Validator feedback: verdict missing" in prompts[0]


def test_publish_cached_result_does_not_mutate(monkeypatch):
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_: (_ for _ in ()).throw(AssertionError("no mutation")))
    out=publish_pr_review.publish(cfg=_cfg(),repo="a/b",pr=7,evidence={"head_sha":"abc"},selected={"route":"cached","decision":{"verdict":"request_changes"},"merge_ok":False},live=True)
    assert out["decision"]["verdict"] == "request_changes"
    assert out["execution"] == {"source":"cache"}


def test_exhausted_invalid_review_publishes_terminal_not_approval(monkeypatch):
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_:True)
    monkeypatch.setattr(publish_pr_review,"runner",lambda *_:object())
    applied=[]
    monkeypatch.setattr(publish_pr_review,"publish_fail_closed",lambda *_args,**_kwargs:applied.append(True) or True)
    out=publish_pr_review.publish(cfg=_cfg(),repo="a/b",pr=7,evidence={"head_sha":"abc"},selected={"route":"needs_human","reason":"invalid_review_json_exhausted","validation_error":"bad"},live=True)
    assert out["decision"] == {"verdict":"needs_human"}
    assert out["merge_ok"] is False and applied == [True]


def test_publish_styles_public_comment_after_structural_decision(monkeypatch):
    cfg=SimpleNamespace(
        max_request_changes_per_pr=2,
        review_style_for=lambda repo: "en+kofte",
    )
    monkeypatch.setattr(publish_pr_review,"mutations_allowed",lambda **_:True)
    monkeypatch.setattr(publish_pr_review,"runner",lambda *_:object())
    published=[]
    monkeypatch.setattr(
        publish_pr_review,
        "publish_decision",
        lambda *_args,**kwargs: published.append(kwargs),
    )
    out=publish_pr_review.publish(
        cfg=cfg,
        repo="a/b",
        pr=7,
        evidence={"head_sha":"abc"},
        selected={"route":"publish","decision":{"verdict":"approve","summary":"Ready."}},
        live=True,
    )
    assert out["decision"]["verdict"] == "approve"
    assert published[0]["style_target"] == "en+kofte"


def test_evidence_agent_receives_only_selected_supplement(monkeypatch, tmp_path):
    cfg=SimpleNamespace(executor_enabled=True)
    monkeypatch.setattr("lokay.config.load_config",lambda _:cfg)
    monkeypatch.setattr(_pr_review_agent_runtime,"agent_execute_allowed",lambda *_args,**_kwargs:True)
    monkeypatch.setattr(_pr_review_agent_runtime,"review_worktree",lambda *_args:tmp_path)
    prompts=[]
    monkeypatch.setattr(_pr_review_agent_runtime,"run_agent",lambda *_args,**kwargs:prompts.append(kwargs["prompt"]) or {"status":"completed","stdout_tail":"{}"})
    evidence={"title":"x","body":"","head":"b","head_sha":"abc","diff":"d","checks_text":""}
    additional={"kind":"diff_tail","value":{"diff":"complete"}}
    out=run_evidence_review_agent.run(config_path=None,repo="a/b",pr=7,evidence=evidence,live=True,additional=additional)
    assert out["ok"] is True
    assert '"kind": "diff_tail"' in prompts[0]
    assert "only evidence collection round" in prompts[0]


def test_verify_supplement_rejects_changed_sha(monkeypatch):
    from lokay.proc import verify_review_evidence_sha
    monkeypatch.setattr(verify_review_evidence_sha,"runner",lambda:object())
    monkeypatch.setattr(verify_review_evidence_sha,"gh_json",lambda *_args,**_kwargs:{"headRefOid":"new"})
    out=verify_review_evidence_sha.verify(repo="a/b",pr=7,expected_sha="old",live=True)
    assert out["ok"] is True and out["route"] == "needs_human"
    assert out["expected_sha"] == "old" and out["actual_sha"] == "new"


def test_missing_selected_evidence_routes_human_without_agent(monkeypatch):
    from lokay.organ.review_boundary import handle_review_boundary
    ctx={"repo":"a/b","pr_number":7,"branch":"b","live":True}
    up={
        "collect_pr_review_evidence":{"evidence":{"head_sha":"abc"}},
        "select_pr_review":{"route":"evidence","evidence_kind":"changed_files"},
        "collect_review_changed_files":{"ok":True,"collected":False,"reason":"unavailable"},
    }
    out=handle_review_boundary("verify_review_evidence_sha",{},up,ctx)
    assert out == {"ok":True,"route":"needs_human","reason":"requested_review_evidence_unavailable"}
