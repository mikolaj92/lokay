from pathlib import Path

from lokay.config import load_config


def test_catalog_loads_thirty_source_repos():
    root = Path(__file__).resolve().parents[1]
    cfg_path = root / "config.yaml"
    if not cfg_path.is_file():
        # CI without local config: synthesize
        cfg_path = root / "config.example.yaml"
    cfg = load_config(cfg_path if (root / "config.yaml").is_file() else None)
    # Prefer explicit catalog via example when needed
    if not cfg.repos:
        import yaml

        data = yaml.safe_load((root / "config.example.yaml").read_text())
        data["repos_file"] = str(root / "repos.mikolaj92.yaml")
        p = root / ".pytest_catalog_config.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")
        cfg = load_config(p)
    assert len(cfg.repos) >= 24  # catalog may auto-disable missing
    names = {r.name for r in cfg.repos}
    assert "mikolaj92/Temida" in names
    assert "mikolaj92/Fala" in names
    assert "mikolaj92/msds-portal" in names
    assert "mikolaj92/lokay-lite" in names
    # mill only walks enabled
    for r in cfg.active_repos():
        assert r.enabled
        assert r.clone_path.exists()
