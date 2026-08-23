"""Small Unix processes at the PR-review entropy boundary."""

from types import SimpleNamespace

from lokay.proc import publish_pr_review, run_pr_review_agent


def _cfg():
    return SimpleNamespace(max_request_changes_per_pr=2)


def test_retry_agent_receives_validator_feedback(monkeypatch, tmp_path):
    cfg=SimpleNamespace(executor_enabled=True)
    monkeypatch.setattr("lokay.config.load_config",lambda _:cfg)
    monkeypatch.setattr(run_pr_review_agent,"agent_execute_allowed",lambda *_args,**_kwargs:True)
    monkeypatch.setattr(run_pr_review_agent,"review_worktree",lambda *_args:tmp_path)
    prompts=[]
    monkeypatch.setattr(run_pr_review_agent,"run_agent",lambda *_args,**kwargs:prompts.append(kwargs["prompt"]) or {"status":"completed","stdout_tail":"{}"})
    evidence={"title":"x","body":"","head":"b","head_sha":"abc","diff":"d","checks_text":""}
    out=run_pr_review_agent.run_review_agent(config_path=None,repo="a/b",pr=7,evidence=evidence,live=True,feedback={"validation_error":"verdict missing","agent_stdout_tail":"{}"})
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
