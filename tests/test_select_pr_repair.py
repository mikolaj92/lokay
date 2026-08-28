from lokay.proc.select_pr_repair import select


def _picked() -> dict:
    return {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}


def test_disabled_department_leaves_feedback_without_repair() -> None:
    out = select(
        _picked(),
        {"triage": {"repairable": True, "reason": "review_requested_changes"}},
        enabled=False,
    )
    assert out == {
        "ok": True,
        "route": "skip",
        "reason": "pr_repair_disabled",
        "repairable": True,
    }


def test_enabled_department_repairs_only_after_triage_verdict() -> None:
    out = select(
        _picked(),
        {
            "triage": {
                "repairable": True,
                "reason": "review_requested_changes",
                "review": {"verdict": "request_changes"},
            }
        },
        enabled=True,
    )
    assert out["route"] == "repair"
    assert out["repo"] == "o/r" and out["pr"] == 9
    assert out["review"] == {"verdict": "request_changes"}


def test_enabled_department_does_not_replace_triage() -> None:
    out = select(_picked(), {"triage": {"merged": True}}, enabled=True)
    assert out["route"] == "skip"
    assert out["reason"] == "triage_did_not_request_repair"
