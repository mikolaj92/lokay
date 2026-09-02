from __future__ import annotations

from pathlib import Path

from lokay.config import load_config
from lokay.proc.factory_begin import run_factory_begin


def test_mikolaj92_catalog_is_preserved_end_to_end(monkeypatch):
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "")
    monkeypatch.setenv("LOKAY_HEALTH_LEASE_PATH", "")
    monkeypatch.setenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", "")
    monkeypatch.delenv("LOKAY_MILL_REPO", raising=False)
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config.yaml")
    names = [repo.name for repo in cfg.active_repos()]
    assert len(names) == len(set(names))
    assert len(names) == len(cfg.repos)
    assert {"mikolaj92/lokay", "mikolaj92/Temida", "mikolaj92/takt"} <= set(names)
    out = run_factory_begin(config_path=str(root / "config.yaml"), live=False)
    assert out == {"ok": True, "live": False}
