"""Existing ai/fix delivery closeout is path success, not condition_not_met."""

from types import SimpleNamespace

from lokay.proc import close_existing_delivery as ced
from lokay.proc.summarize_issue_to_pr import summarize


def test_summarize_existing_closeout_is_delivered_success():
    out = summarize(
        delivery={},
        closeout={"ok": True, "delivered": True, "pr": 42, "reason": "delivery_pr_exists"},
        no_effect={"reason": "condition_not_met"},  # Fala skip noise
    )
    assert out["ok"] is True
    result = out["result"]
    assert result["delivered"] is True
    assert result["pr"] == 42
    assert result.get("stopped") is not True
    assert result["reason"] == "delivery_pr_exists"


def test_summarize_ignores_condition_not_met_when_no_closeout():
    out = summarize(
        delivery={},
        closeout={},
        no_effect={"reason": "condition_not_met"},
    )
    assert out["result"]["stopped"] is True
    assert out["result"]["reason"] == "no_delivery"
    assert out["result"]["delivered"] is False


def test_summarize_no_effect_issue_closed():
    out = summarize(
        delivery={},
        closeout={},
        no_effect={"stopped": True, "reason": "issue_closed"},
    )
    assert out["result"] == {
        "stopped": True,
        "reason": "issue_closed",
        "delivered": False,
    }


def test_close_open_ai_fix_pr_is_delivered(monkeypatch):
    monkeypatch.setattr(
        ced, "load_cfg", lambda _: SimpleNamespace(config_path=None)
    )
    monkeypatch.setattr(ced, "mutations_allowed", lambda **_: True)
    monkeypatch.setattr(ced, "runner", lambda _: object())
    monkeypatch.setattr(
        ced,
        "find_pr_fixing_issue",
        lambda *_a, **_k: {"number": 99, "headRefName": "ai/fix/1019"},
    )
    monkeypatch.setattr(
        ced, "_park_ready", lambda **_k: {"ok": True, "removed": True}
    )
    out = ced.close(repo="o/r", issue=7, config_path=None, live=True)
    assert out["delivered"] is True
    assert out["pr"] == 99
    assert out["reason"] == "delivery_pr_exists"


def test_close_uses_resolved_pr_without_refetch(monkeypatch):
    monkeypatch.setattr(
        ced, "load_cfg", lambda _: SimpleNamespace(config_path=None)
    )
    monkeypatch.setattr(ced, "mutations_allowed", lambda **_: True)

    def boom(*_a, **_k):
        raise AssertionError("must not refetch when pr given")

    monkeypatch.setattr(ced, "find_pr_fixing_issue", boom)
    monkeypatch.setattr(
        ced, "_park_ready", lambda **_k: {"ok": True, "removed": False}
    )
    out = ced.close(
        repo="o/r", issue=7, config_path=None, live=True, pr={"number": 12}
    )
    assert out["delivered"] is True and out["pr"] == 12
