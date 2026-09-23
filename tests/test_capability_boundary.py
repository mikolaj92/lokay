from pathlib import Path

import os

from lokay.capabilities import coding_path, executor_environment, authorize_effect

# HOME is the harness home. GitHub credentials stay out.
_AGENT_ENV_KEYS = frozenset({"PATH", "HOME", "LOKAY_CAPABILITIES"})


def _assert_agent_env_allowlist(env: dict[str, str]) -> None:
    assert set(env) <= _AGENT_ENV_KEYS
    assert not any(k.startswith("GH_") or k.startswith("GITHUB_") for k in env)


def test_builder_has_code_write_but_no_github_credentials_or_merge(tmp_path: Path):
    env = executor_environment(
        "builder",
        {
            "GH_TOKEN": "secret",
            "GITHUB_TOKEN": "also",
            "GH_HOST": "github.com",
            "GH_ENTERPRISE_TOKEN": "ent",
            "LOKAY_HEALTH_LEASE": "lease",
            "PATH": "/bin",
            "HOME": "/tmp/home",
        },
    )
    assert env["LOKAY_CAPABILITIES"] == "code.write"
    assert env["PATH"] == coding_path("/bin")
    assert env["HOME"] == "/tmp/home"
    _assert_agent_env_allowlist(env)
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert "LOKAY_HEALTH_LEASE" not in env
    assert not authorize_effect("builder", "pr.merge")["allowed"]
    assert not authorize_effect("builder", "acceptance.write")["allowed"]


def test_reviewer_has_no_github_credentials():
    env = executor_environment(
        "reviewer",
        {
            "GH_TOKEN": "x",
            "GITHUB_TOKEN": "y",
            "PATH": "/usr/bin:/bin",
        },
    )
    _assert_agent_env_allowlist(env)
    assert "GH_TOKEN" not in env
    assert env["LOKAY_CAPABILITIES"] == "evidence.read,verdict.propose"
    assert coding_path("/usr/bin:/bin") == env["PATH"]
    assert not authorize_effect("reviewer", "git.push")["allowed"]


def test_agent_env_keys_are_allowlist_only():
    ambient = {
        "GH_TOKEN": "secret",
        "GITHUB_TOKEN": "also",
        "GH_HOST": "github.com",
        "PATH": "/usr/local/bin:/bin",
        "USER": "lokay",
        "HOME": "/home/lokay",
    }
    for role in ("builder", "reviewer"):
        env = executor_environment(role, ambient)
        _assert_agent_env_allowlist(env)
        assert env["HOME"] == "/home/lokay"
        deny_first = env["PATH"].split(os.pathsep)[0]
        assert (Path(deny_first) / "gh").is_file()


def test_effect_roles_keep_ambient_path_without_deny_bin():
    env = executor_environment(
        "merge_effect",
        {"GH_TOKEN": "secret", "PATH": "/bin"},
    )
    assert env == {"PATH": "/bin", "LOKAY_CAPABILITIES": "pr.merge"}


def test_dedicated_effect_gets_only_authored_authority_and_denial_is_traceable():
    assert authorize_effect("merge_effect", "pr.merge")["allowed"]
    denied = authorize_effect("reviewer", "pr.merge")
    assert denied == {
        "allowed": False,
        "route": "fail_closed",
        "reason": "capability_denied",
        "role": "reviewer",
        "capability": "pr.merge",
        "trace": True,
    }


def test_coding_path_deny_bin_shadows_gh(tmp_path: Path, monkeypatch):
    # deny-bin gh must be first and executable fail-closed
    path = coding_path(str(tmp_path))
    deny_gh = Path(path.split(os.pathsep)[0]) / "gh"
    assert deny_gh.is_file()
    assert deny_gh.stat().st_mode & 0o111


def test_builder_cannot_write_outside_its_worktree(tmp_path: Path):
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    worktree = tmp_path / "work"
    outside = tmp_path / "outside.txt"
    worktree.mkdir()
    config = Config(
        executor_enabled=True,
        agent_command="/Library/Developer/CommandLineTools/usr/bin/python3",
        agent_args=["-c", "open({outside!r}, 'w').write('escaped')".format(outside=str(outside))],
    )
    result = run_agent(Runner(), config, worktree=worktree, prompt="edit", execute=True)
    assert result["status"] == "failed"
    assert not outside.exists()


def test_builder_can_write_inside_its_worktree(tmp_path: Path):
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    worktree = tmp_path / "work"
    worktree.mkdir()
    target = worktree / "inside.txt"
    config = Config(
        executor_enabled=True,
        agent_command="/Library/Developer/CommandLineTools/usr/bin/python3",
        agent_args=["-c", "open({target!r}, 'w').write('inside')".format(target=str(target))],
    )
    result = run_agent(Runner(), config, worktree=worktree, prompt="edit", execute=True)
    assert result["status"] == "completed"
    assert target.read_text() == "inside"


def test_builder_keeps_the_harness_home(tmp_path: Path, monkeypatch):
    """Scratch is TMPDIR. HOME stays the harness home, so its own config resolves."""
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    worktree = tmp_path / "work"
    worktree.mkdir()
    home = tmp_path / "harness-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    config = Config(
        executor_enabled=True,
        agent_command="/Library/Developer/CommandLineTools/usr/bin/python3",
        agent_args=["-c", "import os; from pathlib import Path; Path(os.environ['TMPDIR'], 'note.txt').write_text(os.environ['HOME'])"],
    )
    result = run_agent(Runner(), config, worktree=worktree, prompt="edit", execute=True)
    assert result["status"] == "completed", result
    import os
    root = Path(os.environ.get("TMPDIR") or "/tmp")
    scratch_notes = sorted(
        root.glob("lokay-coding-*/note.txt"), key=lambda p: p.stat().st_mtime
    )
    assert scratch_notes and scratch_notes[-1].read_text() == str(home)


def test_builder_names_unsupported_sandbox(tmp_path: Path, monkeypatch):
    from lokay.agent import AgentError, run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    monkeypatch.setattr("sys.platform", "linux")
    worktree = tmp_path / "work"
    worktree.mkdir()
    config = Config(
        executor_enabled=True,
        agent_command="/Library/Developer/CommandLineTools/usr/bin/python3",
        agent_args=["-c", "print('no')"],
    )
    try:
        run_agent(Runner(), config, worktree=worktree, prompt="edit", execute=True)
    except AgentError as exc:
        assert str(exc) == "sandbox_runtime_unsupported"
    else:
        raise AssertionError("expected sandbox_runtime_unsupported")


