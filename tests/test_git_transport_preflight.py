from pathlib import Path
from types import SimpleNamespace

from lokay import preflight


def repo(tmp_path: Path, name: str = "owner/repo"):
    clone = tmp_path / "repo"
    (clone / ".git").mkdir(parents=True)
    return SimpleNamespace(name=name, clone_path=clone)


def cfg(item):
    return SimpleNamespace(active_repos=lambda: [item])


def completed(code=0, stdout=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr="")


def test_git_transport_rejects_https_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda argv, **kw: completed(stdout="https://github.com/owner/repo.git\n"),
    )
    assert preflight._github_git_transport(cfg(item)) == (False, "non_ssh_origin")


def test_git_transport_proves_ssh_remote_non_interactively(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs.get("env", {})))
        if "get-url" in argv:
            return completed(stdout="git@github.com:owner/repo.git\n")
        return completed()

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (True, "ok")
    assert calls[-1][0][-3:] == ["--exit-code", "origin", "HEAD"]
    assert calls[-1][1]["GIT_TERMINAL_PROMPT"] == "0"
    assert "BatchMode=yes" in calls[-1][1]["GIT_SSH_COMMAND"]


def test_git_transport_retries_transient_ssh_failure_within_bound(tmp_path, monkeypatch):
    item = repo(tmp_path)
    probes = 0

    def run(argv, **kwargs):
        nonlocal probes
        if "get-url" in argv:
            return completed(stdout="git@github.com:owner/repo.git\n")
        probes += 1
        return completed(code=1 if probes == 1 else 0)

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (True, "ok")
    assert probes == 2


def test_git_transport_fails_after_two_ssh_attempts(tmp_path, monkeypatch):
    item = repo(tmp_path)
    probes = 0

    def run(argv, **kwargs):
        nonlocal probes
        if "get-url" in argv:
            return completed(stdout="git@github.com:owner/repo.git\n")
        probes += 1
        assert kwargs["timeout"] == 10
        return completed(code=1)

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (False, "ssh_auth_unavailable")
    assert probes == 2


def test_repair_changes_only_exact_canonical_https_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if "get-url" in argv:
            return completed(stdout="https://github.com/owner/repo.git\n")
        return completed()

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._repair_github_git_transport(cfg(item)) is True
    assert calls[-1][-3:] == ["set-url", "origin", "git@github.com:owner/repo.git"]


def test_repair_does_not_rewrite_foreign_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return completed(stdout="https://example.com/owner/repo.git\n")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._repair_github_git_transport(cfg(item)) is False
    assert len(calls) == 1
