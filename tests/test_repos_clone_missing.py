
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




