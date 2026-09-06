"""#1015: failed verify_acceptance must not deliver."""

from lokay.organ.common import _require_acceptance
from lokay.proc.summarize_issue_delivery import summarize


def test_require_acceptance_skips_paths_without_prepare():
    assert _require_acceptance({}) is None
    assert _require_acceptance({"push": {"ok": True}}) is None


def test_require_acceptance_fails_closed_when_prepare_without_verify():
    out = _require_acceptance({"prepare_acceptance": {"digest": "sha256:x"}})
    assert out["ok"] is False and out["reason"] == "acceptance_missing"
    assert out["accepted"] is False


def test_require_acceptance_fails_closed_on_failed_verdict():
    out = _require_acceptance(
        {
            "prepare_acceptance": {"digest": "sha256:x"},
            "verify_acceptance": {
                "ok": False,
                "accepted": False,
                "route": "repair",
                "failed_evidence": ["test"],
            },
        }
    )
    assert out["ok"] is False and out["reason"] == "acceptance_failed"
    assert out["failed_evidence"] == ["test"]


def test_require_acceptance_passes_when_accepted():
    assert (
        _require_acceptance(
            {
                "prepare_acceptance": {"digest": "sha256:x"},
                "verify_acceptance": {"ok": True, "accepted": True, "route": "publish"},
            }
        )
        is None
    )


def test_summarize_delivery_not_delivered_when_acceptance_failed():
    out = summarize(
        branch={"branch": "ai/fix/1"},
        pr_create={"pr": 9},
        pr_label={},
        acceptance={"accepted": False, "route": "repair", "failed_evidence": ["test"]},
    )
    assert out["ok"] is False
    assert out["result"]["delivered"] is False
    assert out["result"]["reason"] == "acceptance_failed"


def test_summarize_delivery_delivered_only_when_accepted():
    out = summarize(
        branch={"branch": "ai/fix/1"},
        pr_create={"pr": 9},
        pr_label={},
        acceptance={"accepted": True, "route": "publish"},
    )
    assert out["ok"] is True
    assert out["result"]["delivered"] is True


def test_summarize_delivery_missing_acceptance_fail_closed():
    out = summarize(
        branch={"branch": "ai/fix/1"},
        pr_create={"pr": 9},
        pr_label={},
        acceptance={},
    )
    assert out["result"]["delivered"] is False
    assert out["result"]["reason"] == "acceptance_missing"
