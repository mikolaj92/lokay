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
            if list(spec.argv)[1:3] == ["rev-parse", "origin/main"]:
                return _result("a" * 40 + "\n")
            if list(spec.argv)[1:3] == ["rev-parse", "HEAD"]:
                return _result("a" * 40 + "\n")
            if list(spec.argv)[1:3] == ["rev-list", "--count"]:
                return _result("0\n")
            raise AssertionError(spec.argv)

        def run(self, spec, *, live):
            self.calls.append(list(spec.argv))
            if list(spec.argv)[1] == "log":
                return _result()
            if list(spec.argv)[1] == "diff" or list(spec.argv)[1] == "ls-files":
                return _result()
            raise AssertionError(spec.argv)

    run = Run()
    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", lambda: run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args, **_kwargs: {"ok": False, "error": "git refused worktree removal"},
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])

    payload = json.loads(capsys.readouterr().out.strip())
    assert code == 1
    assert payload["ok"] is False
    assert "self-repair worktree remove failed" in payload["error"]
    assert corner.is_dir()
    assert not any(call[1:3] == ["worktree", "add"] for call in run.calls)


def test_prepare_resumes_owned_dirty_worktree_on_current_base(
    tmp_path, monkeypatch, capsys
):
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
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] == ["rev-parse", "origin/main"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-parse", "HEAD"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("0\n")
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1] == "log":
                return _result()
            if argv[1] == "diff" or argv[1] == "ls-files":
                return _result("src/lokay/partial.py\n")
            if argv[1:3] == ["merge-base", "--is-ancestor"]:
                return _result()
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must resume dirty work")),
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["resumed"] is True
    assert payload["base_sha"] == "a" * 40
    assert corner.is_dir()


def test_prepare_preserves_dirty_worktree_when_current_base_is_not_ancestor(
    tmp_path, monkeypatch, capsys
):
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
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] == ["rev-parse", "origin/main"]:
                return _result("b" * 40 + "\n")
            if argv[1:3] == ["rev-parse", "HEAD"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("0\n")
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1] == "log":
                return _result()
            if argv[1] == "diff" or argv[1] == "ls-files":
                return _result("src/lokay/partial.py\n")
            if argv[1:3] == ["merge-base", "--is-ancestor"]:
                return _result(returncode=1)
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must preserve dirty work")),
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 1
    assert "outside current origin/main" in payload["error"]
    assert corner.is_dir()


def test_prepare_resumes_clean_committed_candidate(tmp_path, monkeypatch, capsys):
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
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] == ["rev-parse", "origin/main"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-parse", "HEAD"]:
                return _result("c" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("1\n")
            if argv[1] == "log" and "--format=%s" in argv:
                return _result("self-repair: deadbeef\n")
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1] == "log":
                if "--format=%s" in argv:
                    return _result("self-repair: deadbeef\n")
                return _result()
            if argv[1] == "diff" or argv[1] == "ls-files":
                return _result()
            if argv[1:3] == ["merge-base", "--is-ancestor"]:
                return _result()
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must resume committed work")),
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["resumed"] is True
    assert payload["candidate_commit"] == "c" * 40
    assert payload["base_sha"] == "a" * 40
    assert corner.is_dir()


def test_prepare_preserves_unrecognized_committed_candidate(
    tmp_path, monkeypatch, capsys
):
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
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] == ["rev-parse", "origin/main"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-parse", "HEAD"]:
                return _result("c" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("1\n")
            if argv[1] == "log" and "--format=%s" in argv:
                return _result("unrelated commit\n")
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1] == "log" or argv[1] == "diff" or argv[1] == "ls-files":
                return _result()
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must preserve candidate")),
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 1
    assert "unrecognized committed" in payload["error"]
    assert corner.is_dir()


def test_prepare_recreates_confirmed_empty_existing_worktree(
    tmp_path, monkeypatch, capsys
):
    clone = tmp_path / "clone"
    clone.mkdir()
    fingerprint = "deadbeef"
    corner = tmp_path / "wt" / "_self_repair" / fingerprint
    corner.mkdir(parents=True)
    cfg = SimpleNamespace(
        active_repos=lambda: [SimpleNamespace(name=prepare.REPO, clone_path=clone)],
        worktrees_root=tmp_path / "wt",
    )
    added: list[list[str]] = []

    class Run:
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] in (["rev-parse", "origin/main"], ["rev-parse", "HEAD"]):
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("0\n")
            if argv[1:3] == ["worktree", "add"]:
                added.append(argv)
                return _result()
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1] == "log" or argv[1] == "diff" or argv[1] == "ls-files":
                return _result()
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)

    def remove(*_args, **_kwargs):
        corner.rmdir()
        return {"ok": True, "removed": True}

    monkeypatch.setattr(prepare, "remove_worktree", remove)

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["base_sha"] == "a" * 40
    assert added and added[0][1:3] == ["worktree", "add"]


def test_prepare_preserves_plan_only_committed_candidate(
    tmp_path, monkeypatch, capsys
):
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
        def run_checked(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:4] == ["remote", "get-url", "origin"]:
                return _result("https://github.com/mikolaj92/lokay.git\n")
            if argv[1:3] == ["fetch", "origin"]:
                return _result()
            if argv[1:3] == ["rev-parse", "origin/main"]:
                return _result("a" * 40 + "\n")
            if argv[1:3] == ["rev-parse", "HEAD"]:
                return _result("c" * 40 + "\n")
            if argv[1:3] == ["rev-list", "--count"]:
                return _result("1\n")
            raise AssertionError(argv)

        def run(self, spec, *, live):
            argv = list(spec.argv)
            if argv[1:3] == ["ls-files", "--others"]:
                return _result(".lokay/approach.md\n")
            if argv[1] == "log" or argv[1] == "diff":
                return _result()
            raise AssertionError(argv)

    monkeypatch.setattr(prepare, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(prepare, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(prepare, "runner", Run)
    monkeypatch.setattr(prepare, "worktree_owned_by_clone", lambda *_args: True)
    monkeypatch.setattr(
        prepare,
        "remove_worktree",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must preserve worktree")),
    )

    code = prepare.main(["--live", "--fingerprint", fingerprint])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 1
    assert "uncommitted plan evidence" in payload["error"]
    assert corner.is_dir()
