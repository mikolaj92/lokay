from __future__ import annotations

from pathlib import Path

from lokay.config import load_config
from lokay.proc.factory_begin import run_factory_begin


def test_mikolaj92_catalog_is_preserved_end_to_end(monkeypatch):
    monkeypatch.delenv("LOKAY_MILL_REPO", raising=False)
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config.yaml")
    names = [repo.name for repo in cfg.active_repos()]
    assert len(names) == len(set(names)) == 30
    assert {"mikolaj92/lokay", "mikolaj92/Temida", "mikolaj92/takt"} <= set(names)
    from lokay.proc import factory_begin
    monkeypatch.setattr(factory_begin, "run_preflight", lambda *_a, **_k: {"ok": True})
    out = run_factory_begin(config_path=str(root / "config.yaml"), live=False)
    assert out["planned"][0]["repos"] == names
