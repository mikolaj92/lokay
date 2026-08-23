"""Structured agent brains for intake / queue_conflict / localize."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.agent import build_agent_argv, session_id_for_worktree
from lokay.config import Config
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
    assert v.semantic["source"] == "agent"


def test_parse_queue_conflict_rejects_needs_human():
    with pytest.raises(Exception):
        parse_queue_conflict_output('{"outcome":"needs_human"}')


def test_existing_localize_json_skips_semantic_agent(tmp_path: Path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n", encoding="utf-8")
    loc_dir = tmp_path / ".lokay"
    loc_dir.mkdir()
    (loc_dir / "localize.json").write_text(
        '{"paths":["src/a.py"],"source":"deterministic"}\n',
        encoding="utf-8",
    )

    def boom(*_args, **_kwargs):
        raise AssertionError("semantic localize must not start when localize.json has paths")

    import lokay.localize_agent as localize_agent

    monkeypatch.setattr(localize_agent, "run_agent", boom)
    loc = build_localization_with_agent(
        runner=_FakeRunner('{"paths":["src/a.py"]}'),
        config=_cfg(),
        execute=True,
        worktree=tmp_path,
        seed_text="Change src/a.py",
    )
    assert "src/a.py" in loc.paths
    assert loc.semantic["source"] == "existing"
    assert loc.semantic["status"] == "completed"


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
    assert loc.semantic["source"] == "agent"


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
    assert loc.semantic["source"] == "fallback"
    assert loc.semantic["status"] == "invalid_json"


def test_localize_drops_numeric_pseudopath_and_broad_directory(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a\n", encoding="utf-8")
    runner = _FakeRunner('{"paths":["291/303/321", "src", "src/a.py"]}')
    loc = build_localization_with_agent(
        runner=runner,
        config=_cfg(),
        execute=True,
        worktree=tmp_path,
        seed_text="Fix the parser.",
    )
    assert "291/303/321" not in loc.paths
    assert "src" not in loc.paths
    assert "src/a.py" in loc.paths


def test_parse_localize_requires_paths():
    with pytest.raises(Exception):
        parse_localize_output('{"paths":[]}')
