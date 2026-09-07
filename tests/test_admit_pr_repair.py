"""admit_pr_repair fail-closes MERGED (#1073)."""

from lokay.proc.admit_pr_repair import admit


def test_admit_skips_merged() -> None:
    out = admit(
        {
            "ok": True,
            "route": "merged",
            "merged": True,
            "state": "MERGED",
            "repo": "o/r",
            "pr": 1072,
        }
    )
    assert out["route"] == "skip"
    assert out["reason"] == "pr_already_merged"
    assert out["merged"] is True


def test_admit_skips_closed() -> None:
    out = admit({"ok": True, "route": "closed", "repo": "o/r", "pr": 1, "state": "CLOSED"})
    assert out["route"] == "skip"
    assert out["reason"] == "pr_closed"


def test_admit_opens_on_open() -> None:
    out = admit({"ok": True, "route": "open", "repo": "o/r", "pr": 1, "state": "OPEN"})
    assert out["route"] == "open"


def test_admit_fail_open_on_unavailable() -> None:
    out = admit(
        {
            "ok": True,
            "route": "unavailable",
            "reason": "pr_view_failed",
            "repo": "o/r",
            "pr": 1,
            "merged": False,
        }
    )
    assert out["route"] == "open"
