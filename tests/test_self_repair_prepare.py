"""Self-repair worktree removal shares the confirmed-ownership guard."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc import self_repair_prepare as prepare


def _result(stdout: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_prepare_refuses_unconfirmed_existing_worktree(tmp_path, monkeypatch, capsys):
    clone = tmp_path / "clone"
    clone.mkdir()
    fingerprint = "deadbeef"
    corner = tmp_path / "wt" / "_self_repair" / fingerprint
    corner.mkdir(parents=True)
    cfg = SimpleNamespace(
        active_repos=lambda: [SimpleNamespace(name=prepare.REPO, clone_path=clone)],
        worktrees_root=tmp_path / "wt",
    )

    class Run:
        def __init__(self):
            self.calls = []

        def run_checked(self, spec, *, live):
            self.calls.append(list(spec.argv))
            if list(spec.argv)[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if list(spec.argv)[1:3] == ["fetch", "origin"]:
                return _result()
            raise AssertionError(spec.argv)

        def run(self, spec, *, live):
            self.calls.append(list(spec.argv))
            if list(spec.argv)[1] == "log":
                return _result()
            raise AssertionError(spec.argv)

    run = Run()
    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", lambda: run)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: {"ok": False, "error": "git refused worktree removal"},
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])

    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 1
    assert payload["ok"] is False
    assert "self-repair worktree remove failed" in payload["error"]
    assert corner.is_dir()
    assert not any(call[1:3] == ["worktree", "add"] for call in run.calls)
