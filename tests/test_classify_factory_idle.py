"""Authored idle classify. Compose still hosts Fala."""

from pathlib import Path

from lokay.proc.classify_factory_idle import classify


def _idle_receipt() -> dict:
    return {
        "health": "idle",
        "idle": True,
        "remaining": {"inbox": 0, "ready": 0, "open_ai_prs": 0},
    }


def test_fresh_stamp_and_empty_lists_route_idle(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    out = classify(live=True, stamp=stamp, receipt=_idle_receipt())
    assert out["route"] == "idle"
    assert out["lane"] == "idle"
    assert out["reason"] == "recent_empty_survey"
    assert out["skipped"] is True


def test_unlabeled_product_remaining_cannot_idle(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    out = classify(
        live=True,
        stamp=stamp,
        receipt={
            "health": "idle",
            "idle": True,
            "remaining": {
                "inbox": 0,
                "ready": 1,
                "open_ai_prs": 0,
                "by_repo": [{"repo": "mikolaj92/Temida", "ready": 1, "occupied": False}],
            },
        },
    )
    assert out == {"ok": True, "route": "host"}


def test_missing_stamp_hosts(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    out = classify(live=True, stamp=stamp, receipt=_idle_receipt())
    assert out == {"ok": True, "route": "host"}


def test_dry_run_hosts(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    assert classify(live=False, stamp=stamp, receipt=_idle_receipt())["route"] == "host"
