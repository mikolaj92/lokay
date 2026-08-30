"""issues_launch_pr: preserve route; live receipt consumes the occupied repo."""

from lokay.proc.launch_issue_to_pr import launch


CANDIDATE = {
    "ok": True,
    "route": "do",
    "repo": "mikolaj92/Temida",
    "issue": 5191,
    "leftover": 4,
    "leftover_issues": [
        {"repo": "mikolaj92/Temida", "issue": 5191},
        {"repo": "mikolaj92/Temida", "issue": 5190},
        {"repo": "mikolaj92/Fala", "issue": 186},
        {"repo": "mikolaj92/Posejdon", "issue": 46},
    ],
}


def test_live_receipt_does_not_overwrite_route_with_do(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": "cannot reserve issue_to_pr receipt: cannot lock issue_to_pr receipts: existing issue_to_pr receipt is still live",
            "repo": "mikolaj92/Temida",
            "issue": 5191,
        },
    )
    out = launch(CANDIDATE, config_path=None)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["issue"] == 5191
    assert [row["issue"] for row in out["leftover_issues"]] == [186, 46]
    assert out["leftover"] == 2


def test_started_launch_drops_the_occupied_repo(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: {
            "ok": True,
            "detached": True,
            "pid": 9,
            "repo": "mikolaj92/Temida",
            "issue": 5191,
        },
    )
    out = launch(CANDIDATE, config_path=None)
    assert out["route"] == "started"
    assert [row["issue"] for row in out["leftover_issues"]] == [186, 46]
    assert out["leftover"] == 2
