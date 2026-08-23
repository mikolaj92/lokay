import json
from pathlib import Path

from lokay.status_dashboard import dashboard_snapshot


def _config(tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    clone.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text(json.dumps({"ts": "2099-01-01T00:00:00+00:00", "kind": "issue_to_pr", "repo": "o/r", "ok": True, "pr": 2}) + "\n")
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


def test_snapshot_is_local_and_exposes_catalog_and_throughput(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    data = dashboard_snapshot(str(config))
    assert data["catalog"][0]["name"] == "o/r"
    assert data["catalog"][0]["clone_available"] is True
    assert data["throughput"]["24h"]["starts"] == 1
    assert data["throughput"]["24h"]["prs"] == 1
    assert data["status"]["survey"] is False
