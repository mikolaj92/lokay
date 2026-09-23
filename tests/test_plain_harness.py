"""Lokay supplies a task and cwd; the harness owns its runtime."""
import json
import os
import sys
from pathlib import Path

from lokay.agent import build_agent_argv, run_agent
from lokay.config import Config, load_config
from lokay.runner import Runner


def test_default_and_shipped_executor_only_pass_the_task():
    root = Path(__file__).resolve().parents[1]
    configs = [Config(), *(load_config(root / name) for name in (
        "config.example.yaml", "config.live-autonomous.example.yaml"
    ))]
    for cfg in configs:
        assert build_agent_argv(cfg, worktree=root, prompt="task") == ["pi", "-p", "task"]
        assert not hasattr(cfg, "agent_model")


def test_real_harness_inherits_runtime_and_can_lock_its_settings(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HARNESS_RUNTIME_MARKER", "inherited")
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "host-only")
    script = tmp_path / "harness.py"
    script.write_text("""import json, os, pathlib, sys
home = pathlib.Path.home()
(home / 'settings.json.lock').mkdir()
print(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'home': str(home),
                  'path': os.environ.get('PATH'), 'tmp': os.environ.get('TMPDIR'),
                  'marker': os.environ.get('HARNESS_RUNTIME_MARKER'),
                  'lease': os.environ.get('LOKAY_HEALTH_LEASE')}))
""")
    cfg = Config(executor_enabled=True, agent_command=sys.executable,
                 agent_args=[str(script), "{prompt}"])
    out = run_agent(Runner(), cfg, worktree=work, prompt="task", execute=True,
                    attach_collector_boundary=False, session_policy="fresh",
                    repo="o/r", issue=1, branch="fix/1", head_sha="abc")
    assert out["status"] == "completed", out
    assert json.loads(out["result_stdout"]) == {
        "argv": ["task"], "cwd": str(work.resolve()), "home": str(home),
        "path": os.environ.get("PATH"), "tmp": os.environ.get("TMPDIR"),
        "marker": "inherited", "lease": "",
    }
    assert (home / "settings.json.lock").is_dir()
    assert out["session"] == ""
    assert out["session_receipt"] == ""
    assert os.environ["LOKAY_HEALTH_LEASE"] == "host-only"
