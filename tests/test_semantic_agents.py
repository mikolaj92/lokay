"""Structured agent brains for intake / queue_conflict / localize."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.agent import build_agent_argv, session_id_for_worktree
from lokay.config import Config
from lokay.intake import decide_intake
from lokay.intake_agent import decide_intake_with_agent, parse_intake_output
from lokay.localize_agent import build_localization_with_agent, parse_localize_output
from lokay.models import Issue
from lokay.queue_conflict import CLOSE, READY
from lokay.queue_conflict_agent import (
    evaluate_queue_conflict_with_agent,
    parse_queue_conflict_output,
)


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/lib",
        number=12,
        title="Fix parser",
        body="Handle empty input in parse().",
        labels=["ai:ready"],
        assignees=["mikolaj92"],
        url="https://example.test/12",
        state="OPEN",
        author="mikolaj92",
    )
    base.update(kwargs)
    return Issue(**base)


def _cfg() -> Config:
    return Config(
        agent="pi",
        agent_command="pi",
        agent_args=["-p", "{prompt}", "--session-id", "{session}"],
        executor_enabled=True,
        mode="live",
    )


class _FakeRunner:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode
        self.specs = []

    def run(self, spec, *, live: bool):
        self.specs.append(spec)
        return type(
            "Result",
            (),
            {
                "returncode": self.returncode,
                "stdout": self.stdout,
                "stderr": "",
                "timed_out": False,
            },
        )()


def test_semantic_sessions_do_not_share_coding_session(tmp_path: Path):
    code = session_id_for_worktree(tmp_path)
    intake = session_id_for_worktree(tmp_path, kind="intake")
    queue = session_id_for_worktree(tmp_path, kind="queue")
    loc = session_id_for_worktree(tmp_path, kind="localize")
    assert code.startswith("lokay-")
    assert intake != code and intake.endswith("-intake")
    assert queue.endswith("-queue")
    assert loc.endswith("-localize")
    argv = build_agent_argv(
        _cfg(), worktree=tmp_path, prompt="judge", session_kind="intake"
    )
    assert argv[-1] == intake


def test_parse_intake_fenced_json():
    parsed = parse_intake_output(
        '```json\n{"decision":"ready","reason":"single_bug","evidence":["one fix"],'
        '"summary":"ok"}\n```'
    )
    assert parsed["decision"] == "ready"
    assert parsed["reason"] == "single_bug"


def test_parse_intake_rejects_unknown_verdict():
    with pytest.raises(Exception):
        parse_intake_output('{"decision":"ship_it"}')


def test_hard_covering_pr_beats_agent_ready(tmp_path: Path):
    runner = _FakeRunner('{"decision":"ready","reason":"looks_fine","summary":"x"}')
    d = decide_intake_with_agent(
        _issue(),
        runner=runner,
        config=_cfg(),
        execute=True,
        clone_path=tmp_path,
        covering_prs=[{"number": 44, "state": "OPEN", "merged": False}],
    )
    assert d.decision == "close"
    assert d.reason == "duplicate_ai_pr_for_issue"
    assert runner.specs == []


def test_agent_ready_overrides_shape_regex_when_json_valid(tmp_path: Path):
    (tmp_path / "README.md").write_text("A pure library kit.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="kit"\n', encoding="utf-8")
    issue = _issue(
        title="Adopt product_shell / Basecoat host stack",
        body="Wire product_shell and /static/platform for auth chrome.",
    )
    assert decide_intake(issue, clone_path=tmp_path).decision == "close"
    runner = _FakeRunner(
        '{"decision":"ready","reason":"operator_wants_host_chrome","evidence":["intentional"],'
        '"summary":"keep"}'
    )
    d = decide_intake_with_agent(
        issue,
        runner=runner,
        config=_cfg(),
        execute=True,
        clone_path=tmp_path,
    )
    assert d.decision == "ready"
    assert d.implementable is True
    assert runner.specs


def test_bad_intake_json_falls_back_to_deterministic(tmp_path: Path):
    (tmp_path / "README.md").write_text("A pure library kit.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="kit"\n', encoding="utf-8")
    issue = _issue(
        title="Adopt product_shell / Basecoat host stack",
        body="Wire product_shell and /static/platform for auth chrome.",
    )
    runner = _FakeRunner("not json at all")
    d = decide_intake_with_agent(
        issue,
        runner=runner,
        config=_cfg(),
        execute=True,
        clone_path=tmp_path,
    )
    assert d.decision == "close"
    assert d.reason == "wrong_product_shape"


def test_queue_covering_pr_still_closes_without_agent():
    v = evaluate_queue_conflict_with_agent(
        _issue(number=12),
        runner=None,
        config=None,
        execute=False,
        open_prs=[{"number": 99, "head_ref": "ai/fix/12-x", "title": "x", "body": ""}],
    )
    assert v.outcome == CLOSE
    assert v.reason == "open_ai_pr_covers_issue"


def test_queue_agent_can_keep_ready_when_heuristics_skip():
    runner = _FakeRunner(
        '{"outcome":"ready","reason":"different_modules","summary":"no real overlap"}'
    )
    v = evaluate_queue_conflict_with_agent(
        _issue(number=9, body="Also edit `src/lokay/cli.py`\n"),
        runner=runner,
        config=_cfg(),
        execute=True,
        peer_issues=[
            {
                "number": 4,
                "title": "Touch cli",
                "body": "Edit `src/lokay/cli.py`\n",
                "labels": ["ai:ready"],
            }
        ],
    )
    assert v.outcome == READY
    assert v.reason == "different_modules"


def test_parse_queue_conflict_rejects_needs_human():
    with pytest.raises(Exception):
        parse_queue_conflict_output('{"outcome":"needs_human"}')


def test_localize_agent_keeps_existing_paths_and_drops_fantasy(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n", encoding="utf-8")
    runner = _FakeRunner(
        '{"paths":["src/a.py","src/missing.py","/etc/passwd"],"notes":["scope"]}'
    )
    loc = build_localization_with_agent(
        runner=runner,
        config=_cfg(),
        execute=True,
        worktree=tmp_path,
        seed_text="Change `src/a.py` for the bug.",
    )
    assert loc.source == "agent"
    assert "src/a.py" in loc.paths
    assert "src/missing.py" not in loc.paths
    assert "/etc/passwd" not in loc.paths


def test_localize_bad_json_falls_back(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n", encoding="utf-8")
    runner = _FakeRunner("nope")
    loc = build_localization_with_agent(
        runner=runner,
        config=_cfg(),
        execute=True,
        worktree=tmp_path,
        seed_text="Change `src/a.py` for the bug.",
    )
    assert loc.source == "deterministic"
    assert "src/a.py" in loc.paths


def test_parse_localize_requires_paths():
    with pytest.raises(Exception):
        parse_localize_output('{"paths":[]}')
