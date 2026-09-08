from pathlib import Path

from fastapi.testclient import TestClient

from lokay.proc.status_server import create_app


import pytest


@pytest.fixture(autouse=True)
def isolated_status_journal(tmp_path, monkeypatch):
    # Exercise real Fala without writing the live operator's journal.
    monkeypatch.setattr(
        "lokay.graph_run.path_journal_dir",
        lambda path_id, *args, **kwargs: tmp_path / "fala" / path_id,
    )


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


def test_dashboard_uses_product_shell_platform_assets_and_server_html(
    tmp_path: Path, monkeypatch
):
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
    assert "Lokay health" not in response.text
    assert "Loading…" not in response.text
    assert "/static/platform/" in response.text
    assert 'id="main-content"' in response.text
    assert "cdn.jsdelivr" not in response.text
    assert client.get("/static/platform/basecoat-factory.min.css").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["health"] == "local"


def test_transport_errors_and_health_after_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    with TestClient(create_app(config_path=str(_config(tmp_path)))) as client:
        missing = client.get("/does-not-exist")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Not Found"}
        rejected = client.post("/health", json={"retry": True})
        assert rejected.status_code == 405
        assert rejected.headers["allow"] == "GET"
        health = client.get("/health")
        assert health.status_code == 200
        assert health.headers["content-type"] == "application/json"
        assert health.json()["health"] == "local"


def test_artifact_http_reads_without_computation_and_reloads_replacement(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta, timezone
    from lokay.proc import status_server
    from lokay.status_dashboard import dashboard_snapshot

    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    config = str(_config(tmp_path))
    data = dashboard_snapshot(config)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data))

    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP must not calculate dashboard status")

    monkeypatch.setattr(status_server, "dashboard_snapshot", forbidden)
    with TestClient(create_app(config_path=config, snapshot_path=path)) as client:
        assert client.get("/").status_code == 200
        assert "owner/repo" in client.get("/").text
        health = client.get("/health").json()
        assert health["ok"] is True
        assert health["snapshot_stale"] is False
        assert health["generated_at"] == data["generated_at"]

        data["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        replacement = tmp_path / "replacement.json"
        replacement.write_text(json.dumps(data))
        replacement.replace(path)
        stale = client.get("/health")
        assert stale.status_code == 200
        assert stale.json()["snapshot_stale"] is True
        assert stale.json()["ok"] is False
        page = client.get("/")
        assert page.status_code == 200
        assert "Dane są nieaktualne" in page.text
        assert "działa prawidłowo" not in page.text

        path.write_text("broken private /secret/path")
        for route in ("/", "/health"):
            response = client.get(route)
            assert response.status_code == 503
            assert "private" not in response.text
        path.unlink()
        assert client.get("/health").status_code == 503


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_cli_rejects_invalid_snapshot_age(value, monkeypatch):
    from lokay.proc import status_server

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid configuration must not start server")

    monkeypatch.setattr("uvicorn.run", forbidden)
    with pytest.raises(SystemExit) as error:
        status_server.main(["--max-snapshot-age", value])
    assert error.value.code == 2


def test_cli_passes_snapshot_options(monkeypatch, tmp_path):
    from lokay.proc import status_server

    observed = {}
    app = object()

    def create(**kwargs):
        observed.update(kwargs)
        return app

    def serve(actual, **kwargs):
        assert actual is app
        observed.update(kwargs)

    monkeypatch.setattr(status_server, "create_app", create)
    monkeypatch.setattr("uvicorn.run", serve)
    path = tmp_path / "snapshot.json"
    assert status_server.main(["--snapshot", str(path), "--max-snapshot-age", "90"]) == 0
    assert observed["snapshot_path"] == path
    assert observed["max_snapshot_age"] == 90
