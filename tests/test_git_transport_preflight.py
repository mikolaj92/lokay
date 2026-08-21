from pathlib import Path
from types import SimpleNamespace

from lokay import preflight


def repo(tmp_path: Path, name: str = "mikolaj92/lokay"):
    clone = tmp_path / "repo"
    (clone / ".git").mkdir(parents=True)
    return SimpleNamespace(name=name, clone_path=clone)


def cfg(item, *others):
    return SimpleNamespace(active_repos=lambda: [item, *others])


def completed(code=0, stdout=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr="")


def test_git_transport_never_touches_product_checkout(tmp_path, monkeypatch):
    item = repo(tmp_path)
    product_path = tmp_path / "Temida"
    (product_path / ".git").mkdir(parents=True)
    product = SimpleNamespace(name="mikolaj92/Temida", clone_path=product_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if "get-url" in argv:
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
        return completed()

    monkeypatch.setattr(preflight.subprocess, "run", run)

    assert preflight._github_git_transport(cfg(product, item)) == (True, "ok")
    assert preflight._repair_github_git_transport(cfg(product, item)) is False
    assert calls
    assert all(str(product_path) not in argv for argv in calls)
    assert all(str(item.clone_path) in argv for argv in calls)


def test_git_transport_rejects_https_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda argv, **kw: completed(stdout="https://github.com/mikolaj92/lokay.git\n"),
    )
    assert preflight._github_git_transport(cfg(item)) == (False, "non_ssh_origin")


def test_git_transport_skips_ls_remote_after_caretaker_fetch(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if "get-url" in argv:
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
        raise AssertionError("ls-remote must not run after caretaker host-ff")

    monkeypatch.setenv("LOKAY_HOST_FF_FETCHED", "1")
    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (True, "ok")
    assert calls == [
        ["git", "-C", str(item.clone_path), "remote", "get-url", "origin"]
    ]


def test_git_transport_still_rejects_https_after_caretaker_fetch(tmp_path, monkeypatch):
    item = repo(tmp_path)
    monkeypatch.setenv("LOKAY_HOST_FF_FETCHED", "1")
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda argv, **kw: completed(stdout="https://github.com/mikolaj92/lokay.git\n"),
    )
    assert preflight._github_git_transport(cfg(item)) == (False, "non_ssh_origin")


def test_git_transport_proves_ssh_remote_non_interactively(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs.get("env", {})))
        if "get-url" in argv:
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
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
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
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
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
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
            return completed(stdout="https://github.com/mikolaj92/lokay.git\n")
        return completed()

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._repair_github_git_transport(cfg(item)) is True
    assert calls[-1][-3:] == ["set-url", "origin", "git@github.com:mikolaj92/lokay.git"]


def test_repair_does_not_rewrite_foreign_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return completed(stdout="https://example.com/mikolaj92/lokay.git\n")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._repair_github_git_transport(cfg(item)) is False
    assert len(calls) == 1


def test_git_transport_missing_origin_fails_closed_without_ls_remote(tmp_path, monkeypatch):
    """No origin remote is origin_unavailable, not a protocol lie or a pass."""
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if "get-url" in argv:
            return completed(code=2, stdout="")
        raise AssertionError("ls-remote must not run when origin is missing")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (False, "origin_unavailable")
    assert calls == [
        ["git", "-C", str(item.clone_path), "remote", "get-url", "origin"]
    ]


def test_git_transport_get_url_timeout_is_origin_unavailable(tmp_path, monkeypatch):
    item = repo(tmp_path)

    def run(argv, **kwargs):
        raise preflight.subprocess.TimeoutExpired(cmd=argv, timeout=10)

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (False, "origin_unavailable")


def test_git_transport_rejects_git_protocol_and_noncanonical_ssh(tmp_path, monkeypatch):
    item = repo(tmp_path)
    for origin in (
        "git://github.com/mikolaj92/lokay.git",
        "ssh://git@github.com/mikolaj92/lokay.git",
        "https://github.com/mikolaj92/lokay",
        "git@github.com:mikolaj92/lokay",
        "",
    ):
        def run(argv, origin=origin, **kwargs):
            if "get-url" in argv:
                return completed(stdout=origin + "\n")
            raise AssertionError(f"must not probe ls-remote for {origin!r}")

        monkeypatch.setattr(preflight.subprocess, "run", run)
        assert preflight._github_git_transport(cfg(item)) == (False, "non_ssh_origin"), origin


def test_git_transport_ls_remote_timeout_retries_then_fails_closed(tmp_path, monkeypatch):
    item = repo(tmp_path)
    probes = 0

    def run(argv, **kwargs):
        nonlocal probes
        if "get-url" in argv:
            assert kwargs.get("env", {}).get("GIT_TERMINAL_PROMPT") == "0"
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
        probes += 1
        raise preflight.subprocess.TimeoutExpired(cmd=argv, timeout=10)

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (False, "ssh_auth_unavailable")
    assert probes == 2


def test_git_transport_get_url_is_non_interactive(tmp_path, monkeypatch):
    item = repo(tmp_path)

    def run(argv, **kwargs):
        env = kwargs.get("env") or {}
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
        if "get-url" in argv:
            return completed(stdout="git@github.com:mikolaj92/lokay.git\n")
        assert "BatchMode=yes" in env.get("GIT_SSH_COMMAND", "")
        return completed()

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._github_git_transport(cfg(item)) == (True, "ok")


def test_git_transport_skips_checkout_without_git_dir(tmp_path, monkeypatch):
    """Missing clone is catalog inventory, not a fake transport pass for a real .git."""
    bare = tmp_path / "no-git"
    bare.mkdir()
    item = SimpleNamespace(name="mikolaj92/lokay", clone_path=bare)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no git probe")),
    )
    assert preflight._github_git_transport(cfg(item)) == (True, "ok")


def test_repair_does_not_rewrite_missing_origin(tmp_path, monkeypatch):
    item = repo(tmp_path)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return completed(code=2, stdout="")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    assert preflight._repair_github_git_transport(cfg(item)) is False
    assert all("set-url" not in argv for argv in calls)
