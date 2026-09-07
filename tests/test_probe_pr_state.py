"""probe_pr_state classifies MERGED / CLOSED / OPEN (#1073)."""

from lokay.proc.probe_pr_state import classify_view, probe


def test_classify_merged_via_merged_at() -> None:
    out = classify_view(
        {"number": 1072, "state": "MERGED", "mergedAt": "2026-09-07T06:45:00Z", "headRefName": "ai/fix/1071-x"},
        pr=1072,
    )
    assert out["route"] == "merged"
    assert out["merged"] is True
    assert out["reason"] == "pr_already_merged"
    assert out["state"] == "MERGED"


def test_classify_merged_via_merged_at_even_if_state_closed() -> None:
    out = classify_view(
        {"number": 9, "state": "CLOSED", "mergedAt": "t", "headRefName": "ai/fix/9"},
        pr=9,
    )
    assert out["route"] == "merged"
    assert out["merged"] is True


def test_classify_closed_unmerged() -> None:
    out = classify_view(
        {"number": 9, "state": "CLOSED", "mergedAt": None, "headRefName": "ai/fix/9"},
        pr=9,
    )
    assert out["route"] == "closed"
    assert out["merged"] is False
    assert out["reason"] == "pr_closed"


def test_classify_open() -> None:
    out = classify_view(
        {"number": 9, "state": "OPEN", "mergedAt": None, "headRefName": "ai/fix/9"},
        pr=9,
    )
    assert out["route"] == "open"
    assert out["merged"] is False


def test_offline_probe_assumes_open() -> None:
    out = probe(repo="o/r", pr=9, live=False)
    assert out["route"] == "open"
    assert out["offline"] is True
