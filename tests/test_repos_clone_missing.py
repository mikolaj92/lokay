import json
from types import SimpleNamespace

from lokay.proc import repos_clone_missing


class Config:
    def __init__(self, repos):
        self._repos = repos

    def active_repos(self):
        return self._repos


class Runner:
    def __init__(self):
        self.calls = []

    def run(self, spec, *, live):
        self.calls.append((spec, live))
        return SimpleNamespace(returncode=0, stderr="")


def run_live(monkeypatch, repos):
    runner = Runner()
    monkeypatch.setattr(repos_clone_missing, "load_cfg", lambda args: Config(repos))
    monkeypatch.setattr(repos_clone_missing, "mutations_allowed", lambda **kwargs: True)
    monkeypatch.setattr(repos_clone_missing, "runner", lambda: runner)
    assert repos_clone_missing.main([]) == 0
    return runner


def test_skips_missing_product_repos(monkeypatch, tmp_path, capsys):
    repos = [
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]

    runner = run_live(monkeypatch, repos)

    assert runner.calls == []
    assert json.loads(capsys.readouterr().out)["missing_before"] == 0


def test_clones_missing_lokay_and_skips_products(monkeypatch, tmp_path, capsys):
    repos = [
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/lokay", clone_path=tmp_path / "lokay"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]

    runner = run_live(monkeypatch, repos)

    assert len(runner.calls) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["cloned"] == [
        {"name": "mikolaj92/lokay", "clone_path": str(tmp_path / "lokay")}
    ]
