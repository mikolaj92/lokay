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


def test_template_does_not_reload_independently_of_snapshot_schema():
    from lokay.proc.status_server import TEMPLATES

    assert TEMPLATES.env.auto_reload is False


def test_dashboard_uses_product_shell_platform_assets_and_server_html(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    client = TestClient(create_app(config_path=str(_config(tmp_path))))
    response = client.get("/")
    assert response.status_code == 200
    assert "owner/repo" in response.text
    assert "Obsługiwane repozytoria" in response.text
    assert "Ukończone zadania w ostatniej godzinie" in response.text
    assert "Otwarte zadania do wykonania" in response.text
    assert "Co pozostało do zrobienia" in response.text
    assert "Operator notes" not in response.text
    assert "Mill health" not in response.text
    assert "Loading…" not in response.text
    assert "/static/platform/" in response.text
    assert 'id="main-content"' in response.text
    assert "cdn.jsdelivr" not in response.text
    assert client.get("/static/platform/basecoat-factory.min.css").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["health"] == "local"
