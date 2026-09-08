import json
from pathlib import Path

from lokay.status_dashboard import dashboard_snapshot


def _config(tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    clone.mkdir()
    state = tmp_path / "state.jsonl"
    now = (
        __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat()
    )
    state.write_text(
        json.dumps(
            {"ts": now, "kind": "issue_to_pr", "repo": "o/r", "ok": True, "pr": 2}
        )
        + "\n"
        + json.dumps(
            {
                "ts": now,
                "kind": "pr_triage",
                "repo": "o/r",
                "ok": True,
                "pr": 2,
                "merged": True,
            }
        )
        + "\n"
    )
    (tmp_path / "last-pass.json").write_text(
        json.dumps(
            {
                "kind": "pass_receipt",
                "ts": now,
                "health": "progress",
                "progress": 1,
                "remaining": {
                    "inbox": 3,
                    "ready": 2,
                    "ready_with_open_pr": 1,
                    "open_ai_prs": 1,
                    "review_limbo": 1,
                    "needs_repair": 0,
                    "survey_errors": 0,
                    "by_repo": [{"repo": "o/r", "inbox": 3, "ready": 2}],
                },
            }
        )
    )
    config = tmp_path / "config.yaml"
    config.write_text(f"""mode: live
repos:
  - name: o/r
    clone_path: {clone}
executor:
  enabled: true
  agent: pi
  command: pi
  args: ["--prompt", "{{prompt}}"]
merge:
  enabled: true
state:
  path: {state}
""")
    return config


def test_snapshot_is_local_and_exposes_catalog_and_throughput(
    tmp_path: Path, monkeypatch
):
    config = _config(tmp_path)
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    data = dashboard_snapshot(str(config))
    assert data["catalog"][0]["name"] == "o/r"
    assert data["catalog"][0]["clone_available"] is True
    assert data["throughput"]["1h"]["starts"] == 1
    assert data["throughput"]["1h"]["prs"] == 1
    assert data["throughput"]["1h"]["merges"] == 1
    assert data["kpis"]["issues_per_hour"] == 1
    assert data["kpis"]["open_issues"] == 5
    assert data["backlog"]["ready_with_open_pr"] == 1
    assert data["health"]["label"] == "Lokay pracuje"
    assert data["status"]["survey"] is False


def test_triage_noise_receipt_is_not_pracuje(tmp_path: Path, monkeypatch):
    """health=waiting with a progress counter must not label Lokay pracuje (#1042)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("")
    now = (
        __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat()
    )
    (tmp_path / "last-pass.json").write_text(
        __import__("json").dumps(
            {
                "kind": "pass_receipt",
                "ts": now,
                "health": "waiting",
                "progress": 1,
                "dod_progress": False,
                "outcome": "none",
                "remaining": {
                    "inbox": 0,
                    "ready": 1,
                    "open_ai_prs": 0,
                    "issue_to_pr_started": 0,
                    "survey_errors": 0,
                    "by_repo": [],
                },
            }
        )
    )
    config = tmp_path / "config.yaml"
    config.write_text(f"""mode: live
repos:
  - name: o/r
    clone_path: {clone}
executor:
  enabled: true
  agent: pi
  command: pi
  args: ["--prompt", "{{prompt}}"]
merge:
  enabled: true
state:
  path: {state}
""")
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    data = dashboard_snapshot(str(config))
    assert data["health"]["code"] == "waiting"
    assert data["health"]["label"] != "Lokay pracuje"
    assert data["health"]["label"] == "Oczekiwanie na zewnętrzny wynik"


def test_dashboard_yield_reads_history_once(tmp_path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    from lokay import status_dashboard

    # Keep the native status path out of this yield-only read-count assertion.
    status = status_dashboard.compose_status(config_path=str(config), survey=False)
    monkeypatch.setattr(status_dashboard, "compose_status", lambda **kwargs: status)
    history = tmp_path / "state.jsonl"
    original_open = Path.open
    reads = []

    def count_open(self, *args, **kwargs):
        if self == history:
            reads.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", count_open)
    data = dashboard_snapshot(str(config))

    assert reads == [history]
    for label in ("1h", "24h", "7d"):
        assert data["throughput"][label]["starts"] == 1
        assert data["throughput"][label]["merges"] == 1
