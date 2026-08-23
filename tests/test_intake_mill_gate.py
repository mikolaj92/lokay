"""Mill must not call issue_to_pr when intake rejects a ready issue."""

from __future__ import annotations

from pathlib import Path

from lokay.agent import COLLECTOR_BOUNDARY, run_agent
from lokay.compose import tick
from lokay.config import Config
from lokay.runner import CommandSpec


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(f"""mode: live
repos:
  - name: a/lib
    clone_path: {tmp_path}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: false
  require_checks: false
limits:
  max_triage_per_tick: 0
  max_issues_per_tick: 1
  max_repairs_per_tick: 0
worktrees:
  root: {tmp_path / 'wt'}
state:
  path: {tmp_path / 'state.jsonl'}
""")
    return str(path)


def test_agent_collector_boundary_never_executes_collection(tmp_path: Path):
    """The coding slot may patch a collector, never run or await collection."""
    seen: list[CommandSpec] = []

    class Runner:
        def run(self, spec: CommandSpec, *, live: bool):
            seen.append(spec)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    result = run_agent(
        Runner(),
        Config(
            agent="real-agent",
            agent_command="real-agent",
            agent_args=["--prompt", "{prompt}"],
            executor_enabled=True,
        ),
        worktree=tmp_path,
        prompt="Implement the bounded collector bootstrap patch.",
        execute=True,
    )

    assert result["status"] == "completed"
    assert result["collector_boundary"] is True
    assert len(seen) == 1
    prompt = seen[0].argv[-1]
    assert COLLECTOR_BOUNDARY in prompt
    assert "do not start a collection" in prompt
    assert "must not populate collection data" in prompt
    assert "wait for collection completion" in prompt
