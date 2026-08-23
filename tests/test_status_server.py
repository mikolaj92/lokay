from pathlib import Path

from fastapi.testclient import TestClient

from lokay.proc.status_server import create_app


def _config(tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    clone.mkdir()
    state = tmp_path / "state.jsonl"
    state.write_text("")
    config = tmp_path / "config.yaml"
    config.write_text(f"""mode: live
repos:
  - name: owner/repo
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


def test_dashboard_uses_product_shell_platform_assets_and_server_html(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    client = TestClient(create_app(config_path=str(_config(tmp_path))))
    response = client.get("/")
    assert response.status_code == 200
    assert "owner/repo" in response.text
    assert "Supported repositories" in response.text
    assert "/static/platform/" in response.text
    assert 'id="main-content"' in response.text
    assert "cdn.jsdelivr" not in response.text
    assert client.get("/static/platform/basecoat-factory.min.css").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["health"] == "local"
