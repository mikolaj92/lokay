from pathlib import Path
from lokay.capabilities import coding_path, executor_environment, authorize_effect


def test_builder_has_code_write_but_no_github_credentials_or_merge(tmp_path: Path):
    env = executor_environment(
        "builder",
        {
            "GH_TOKEN": "secret",
            "GITHUB_TOKEN": "also",
            "LOKAY_HEALTH_LEASE": "lease",
            "PATH": "/bin",
        },
    )
    assert env["LOKAY_CAPABILITIES"] == "code.write"
    assert env["PATH"].startswith(coding_path("")) or coding_path("/bin") == env["PATH"]
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert "LOKAY_HEALTH_LEASE" not in env
    assert not authorize_effect("builder", "pr.merge")["allowed"]
    assert not authorize_effect("builder", "acceptance.write")["allowed"]


def test_reviewer_has_no_github_credentials():
    env = executor_environment("reviewer", {"GH_TOKEN": "x", "PATH": "/usr/bin:/bin"})
    assert "GH_TOKEN" not in env
    assert env["LOKAY_CAPABILITIES"] == "evidence.read,verdict.propose"
    assert coding_path("/usr/bin:/bin") == env["PATH"]
    assert not authorize_effect("reviewer", "git.push")["allowed"]


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
    deny_gh = Path(path.split(__import__("os").pathsep)[0]) / "gh"
    assert deny_gh.is_file()
    assert deny_gh.stat().st_mode & 0o111
