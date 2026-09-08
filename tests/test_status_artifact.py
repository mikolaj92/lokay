"""The HTTP artifact boundary never recomputes status."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from lokay import status_artifact


def snapshot(now):
    return {
        "generated_at": now.isoformat(),
        "status": {"ok": True, "health": "local"},
        "health": {"code": "local", "label": "Brak przebiegu", "needs_attention": False},
        "throughput": {}, "kpis": {}, "backlog": {}, "catalog": [], "history": [],
    }


def test_read_retains_data_timestamp_and_marks_age(tmp_path):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    data = snapshot(now - timedelta(seconds=121))
    path = tmp_path / "dashboard.json"
    path.write_text(json.dumps(data))

    loaded = status_artifact.read_snapshot(path, max_age=120, now=now)

    assert loaded["generated_at"] == data["generated_at"]
    assert loaded["status"] == data["status"]
    assert loaded["snapshot_age_seconds"] == 121
    assert loaded["snapshot_stale"] is True
    assert status_artifact.read_snapshot(path, max_age=121, now=now)["snapshot_stale"] is False


@pytest.mark.parametrize("content", [
    "broken", "[]", "{}",
    json.dumps({**snapshot(datetime.now(timezone.utc)), "generated_at": "2026-09-01"}),
    json.dumps({**snapshot(datetime.now(timezone.utc)), "status": []}),
    json.dumps({**snapshot(datetime.now(timezone.utc)), "catalog": [None]}),
    json.dumps({**snapshot(datetime.now(timezone.utc)), "status": {"ok": "yes"}}),
])
def test_invalid_artifact_is_classified_without_fallback(tmp_path, content):
    path = tmp_path / "dashboard.json"
    path.write_text(content)
    with pytest.raises(status_artifact.SnapshotUnavailable):
        status_artifact.read_snapshot(path)


def test_missing_and_oversize_artifacts_are_unavailable(tmp_path):
    path = tmp_path / "dashboard.json"
    with pytest.raises(status_artifact.SnapshotUnavailable):
        status_artifact.read_snapshot(path)
    path.write_bytes(b" " * (status_artifact.MAX_SNAPSHOT_BYTES + 1))
    with pytest.raises(status_artifact.SnapshotUnavailable):
        status_artifact.read_snapshot(path)


def test_future_timestamp_is_unavailable(tmp_path):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    path = tmp_path / "dashboard.json"
    path.write_text(json.dumps(snapshot(now + timedelta(hours=1))))
    with pytest.raises(status_artifact.SnapshotUnavailable):
        status_artifact.read_snapshot(path, now=now)


@pytest.mark.parametrize("changes", [
    {"status": {"ok": True, "last_pass": "not-an-object"}},
    {"status": {"ok": True, "last_pass": {"remaining": []}}},
    {"status": {"ok": True, "by_repo": [None]}},
    {"throughput": {"1h": 7}},
    {"history": [{"remaining": "not-an-object"}]},
])
def test_nested_template_inputs_are_validated(tmp_path, changes):
    data = {**snapshot(datetime.now(timezone.utc)), **changes}
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data))
    with pytest.raises(status_artifact.SnapshotUnavailable):
        status_artifact.read_snapshot(path)
