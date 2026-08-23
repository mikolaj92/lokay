"""Issue #19: rare super-fallbacks deleted or promoted — no zombie shims."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from lokay import gh_prs, graph_run

ROOT = Path(__file__).resolve().parents[1]


def test_no_grok_agent_compat_module():
    """Deleted: lokay.grok_agent backward-compat re-export."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("lokay.grok_agent")
    assert not (ROOT / "src" / "lokay" / "grok_agent.py").exists()


def test_no_pr_checks_green_compat_wrapper():
    """Deleted: pr_checks_green — use pr_checks_report only."""
    assert not hasattr(gh_prs, "pr_checks_green")
    assert callable(gh_prs.pr_checks_report)


def test_no_machine_hardcoded_fala_home_in_graph_run():
    """Deleted: /Users/mikomac/... super-fallback; sibling + FALA_HOME only."""
    src = inspect.getsource(graph_run)
    assert "/Users/mikomac" not in src
    assert "Developer/OSS/Fala" not in src


def test_run_path_fala_home_candidates_are_relative_only():
    """Sibling layout discovery only — no absolute user paths in candidate list."""
    src = inspect.getsource(graph_run.run_path)
    assert 'root.parent / "Fala"' in src or "root.parent / 'Fala'" in src
    assert 'Path("/Users/' not in src


def test_no_runtime_engine_selector():
    """Fala is the only composer; no environment-selected Python graph remains."""
    assert not (ROOT / "src" / "lokay" / "compose" / "_atoms.py").exists()


def test_fallbacks_doc_exists():
    assert (ROOT / "docs" / "FALLBACKS.md").is_file()
    text = (ROOT / "docs" / "FALLBACKS.md").read_text(encoding="utf-8")
    assert "pr_checks_green" in text
    assert "Deleted" in text


def test_tick_fala_triage_noop_does_not_count_as_progress(tmp_path, monkeypatch):
    from lokay.compose import tick as tick_mod

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: live
repos:
  - name: o/r
    clone_path: {tmp_path}
executor:
  enabled: false
limits:
  max_triage_per_tick: 1
  max_issues_per_tick: 0
  max_repairs_per_tick: 0
merge:
  enabled: false
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )

    def fake_atom(main, argv):
        name = getattr(main, "__module__", "")
        if name.endswith("list_inbox"):
            return {"ok": True, "issues": [{"number": 1, "title": "skip"}]}
        if name.endswith("list_issues"):
            return {"ok": True, "issues": []}
        if name.endswith("list_prs"):
            return {"ok": True, "prs": []}
        return {"ok": True}

    monkeypatch.setattr(tick_mod, "run_preflight", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(tick_mod, "_run", fake_atom)

    def fake_ready(**kwargs):
        from lokay.passkit import io as pass_io

        pass_io.write_json(
            pass_io.survey_path(kwargs["pass_dir"]),
            pass_io.read_json(pass_io.working_path(kwargs["pass_dir"])),
        )
        return {
            "ok": True,
            "pass_dir": kwargs["pass_dir"],
            "remaining_ready": 0,
            "survey_errors": 0,
        }

    monkeypatch.setattr(tick_mod, "run_survey_ready", fake_ready)
    monkeypatch.setattr(
        tick_mod,
        "run_path",
        lambda **kwargs: {
            "ok": True,
            "applied": False,
            "skipped": True,
            "decision": {"decision": "skip"},
        },
    )
    monkeypatch.setattr(tick_mod, "run_queue_conflict", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick_mod, "run_resolve_conflicts", lambda **kwargs: {"ok": True}
    )
    monkeypatch.setattr(tick_mod, "run_select_implement", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(
        tick_mod,
        "run_plan_pass",
        lambda **kwargs: __import__(
            "lokay.passkit.io", fromlist=["write_json"]
        ).write_json(
            __import__("lokay.passkit.io", fromlist=["plan_path"]).plan_path(
                kwargs["pass_dir"]
            ),
            {
                "triage_targets": [],
                "closeout_targets": [],
                "implement_candidates": [],
                "triage_budget_remaining": 0,
            },
        )
        and {"ok": True},
    )
    monkeypatch.setattr(
        tick_mod, "run_refresh_occupancy", lambda **kwargs: {"ok": True}
    )
    out = tick_mod.compose_tick(config_path=str(cfg), live=True)
    assert out["progress"] == 0
    assert out["remaining"]["inbox"] == 1
