"""Runner must neutralize host color envs so gh --json stays parseable."""

from __future__ import annotations

import json

from lokay.runner import CommandSpec, Runner, strip_ansi


def test_strip_ansi_removes_sgr():
    colored = '\x1b[1;37m[\x1b[m{"number":31}\x1b[1;37m]\x1b[m'
    plain = strip_ansi(colored)
    assert '\x1b' not in plain
    assert json.loads(plain) == [{"number": 31}]


def test_runner_spec_env_does_not_mutate_parent(monkeypatch):
    import os

    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "parent-token")
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs["env"])
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("lokay.runner.subprocess.run", fake_run)
    Runner().run(
        CommandSpec(argv=("echo",), env={"LOKAY_HEALTH_LEASE": ""}),
        live=True,
    )

    assert captured["LOKAY_HEALTH_LEASE"] == ""
    assert os.environ["LOKAY_HEALTH_LEASE"] == "parent-token"


def test_runner_env_disables_force_color(monkeypatch):
    """Even if host exports FORCE_COLOR/CLICOLOR_FORCE, child env is neutralized."""
    monkeypatch.setenv('FORCE_COLOR', '1')
    monkeypatch.setenv('CLICOLOR_FORCE', '1')
    monkeypatch.setenv('NO_COLOR', '')
    seen: dict[str, str] = {}

    def fake_run(argv, cwd=None, env=None, capture_output=None, text=None, timeout=None, check=None):
        seen.update(env or {})

        class R:
            returncode = 0
            stdout = '[{"ok":true}]'
            stderr = ''

        return R()

    monkeypatch.setattr('lokay.runner.subprocess.run', fake_run)
    r = Runner()
    res = r.run(CommandSpec(argv=('gh', 'issue', 'list', '--json', 'number')), live=True)
    assert res.returncode == 0
    assert seen.get('NO_COLOR') == '1'
    assert seen.get('CLICOLOR_FORCE') == '0'
    assert seen.get('FORCE_COLOR') == '0'
    assert seen.get('GH_FORCE_TTY') == '0'
    assert '\x1b' not in res.stdout
