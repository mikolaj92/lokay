from __future__ import annotations

import json
from pathlib import Path

from lokay.work_units import project_work_units, status_work_units


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_delivery_is_monotonic_across_later_stale_stop(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    _write(
        state,
        [
            {"ts": "2026-09-02T12:21:43Z", "kind": "issue_to_pr", "repo": "a/b", "issue": 308, "run_id": "one", "pr": 309, "delivered": True},
            {"ts": "2026-09-02T12:22:28Z", "kind": "issue_to_pr", "repo": "a/b", "issue": 308, "run_id": "two", "delivered": False, "stopped": True, "reason": "condition_not_met"},
        ],
    )

    units = project_work_units(state)

    assert units == [{
        "work_id": "a/b#308",
        "repo": "a/b",
        "issue": 308,
        "state": "delivered",
        "delivered": True,
        "pr": 309,
        "run_id": "one",
        "updated_at": "2026-09-02T12:21:43Z",
    }]


def test_latest_nonterminal_state_is_kept_before_delivery(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    _write(
        state,
        [
            {"ts": "1", "kind": "issue_to_pr", "repo": "a/b", "issue": 7, "run_id": "one", "work_state": "implementing"},
            {"ts": "2", "kind": "issue_to_pr", "repo": "a/b", "issue": 7, "run_id": "two", "reason": "checks_pending", "delivered": False},
        ],
    )

    assert project_work_units(state)[0]["state"] == "checks_pending"


def test_status_projection_is_bounded_and_keeps_latest_delivery():
    rows = [
        {"work_id": f"a/b#{n}", "repo": "a/b", "issue": n, "state": "delivered", "delivered": True, "pr": n, "updated_at": str(n)}
        for n in range(1, 80)
    ]
    rows.append({"work_id": "a/b#90", "repo": "a/b", "issue": 90, "state": "checks_pending", "delivered": False, "updated_at": "90"})

    visible, latest = status_work_units(rows, limit=20)

    assert len(visible) == 20
    assert any(row["work_id"] == "a/b#90" for row in visible)
    assert latest["work_id"] == "a/b#79"
