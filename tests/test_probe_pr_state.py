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


def test_live_probe_returns_identity_required_for_repair_push_recovery(monkeypatch) -> None:
    from lokay.config import Config
    from lokay.runner import CommandResult

    seen = []
    monkeypatch.setattr("lokay.proc.probe_pr_state.load_config", lambda _path: Config())
    monkeypatch.setattr("lokay.proc.probe_pr_state.runner", lambda _cfg: object())

    def gh_json(_runner, args, *, live: bool):
        seen.append((args, live))
        return {
            "number": 9, "state": "OPEN", "mergedAt": None,
            "headRefName": "ai/fix/9-x", "headRefOid": "b" * 40,
            "headRepository": {"nameWithOwner": "o/r"},
        }

    monkeypatch.setattr("lokay.proc.probe_pr_state.gh_json", gh_json)
    out = probe(repo="o/r", pr=9, live=True, config_path="config.yaml")

    assert out["route"] == "open"
    assert out["head_ref"] == "ai/fix/9-x"
    assert out["head_ref_sha"] == "b" * 40
    assert out["head_repo"] == "o/r"
    assert seen[0][1] is True
    assert "headRefOid" in seen[0][0][-1]
    assert "headRepository{nameWithOwner}" in seen[0][0][-1]


def test_offline_probe_assumes_open() -> None:
    out = probe(repo="o/r", pr=9, live=False)
    assert out["route"] == "open"
    assert out["offline"] is True
