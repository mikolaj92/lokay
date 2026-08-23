"""Mill must not call issue_to_pr when intake rejects a ready issue."""

from __future__ import annotations

from pathlib import Path

from lokay.agent import COLLECTOR_BOUNDARY, run_agent
from lokay.compose import tick
from lokay.config import Config
from lokay.runner import CommandSpec


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""mode: live
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
"""
    )
    return str(path)


def test_ready_without_intake_pass_cannot_implement(tmp_path, monkeypatch):
    config = _config(tmp_path)
    implemented = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [
                    {
                        "number": 9,
                        "repo": "a/lib",
                        "title": "Adopt product_shell",
                        "labels": ["work:ready", "ai:ready"],
                    }
                ],
            }
        if fn is tick.p_intake.main:
                        return {
                "ok": True,
                "implementable": False,
                "applied": True,
                "decision": {"decision": "close", "reason": "wrong_product_shape"},
                "reason": "wrong_product_shape",
            }
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or (_ for _ in ()).throw(AssertionError("issue_to_pr must not run")),
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert implemented == []
    assert any(a.get("step") == "verify_issue_ready" for a in result["actions"])
    assert result["progress"] >= 1


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


def test_intake_ready_allows_issue_to_pr(tmp_path, monkeypatch):
    config = _config(tmp_path)
    implemented = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [
                    {
                        "number": 4,
                        "repo": "a/lib",
                        "title": "Fix parser",
                        "labels": ["work:ready", "ai:ready"],
                    }
                ],
            }
        if fn is tick.p_intake.main:
            return {
                "ok": True,
                "implementable": True,
                "applied": False,
                "decision": {"decision": "ready", "reason": "intake_ok"},
            }
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: implemented.append(kw)
        or {"ok": True, "pr": 7, "branch": "ai/fix/4-fix-parser"},
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert len(implemented) == 1
    assert implemented[0]["issue_number"] == 4
    assert any(a.get("step") == "verify_issue_ready" for a in result["actions"])
