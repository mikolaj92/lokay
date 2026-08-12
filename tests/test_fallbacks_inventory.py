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
    assert "root.parent / \"Fala\"" in src or "root.parent / 'Fala'" in src
    assert "Path(\"/Users/" not in src


def test_no_runtime_engine_selector():
    """Fala is the only composer; no environment-selected Python graph remains."""
    assert not (ROOT / "src" / "lokay" / "compose" / "_atoms.py").exists()


def test_tick_fala_failure_does_not_fall_through_to_atoms(tmp_path: Path, monkeypatch):
    """Deleted: silent except→atom super-fallback when LOKAY_USE_FALA=1."""
    from lokay.compose import tick as tick_mod

    monkeypatch.setenv("LOKAY_USE_FALA", "1")
    for key in (
        "LOKAY_MODE",
        "LOKAY_EXECUTOR_ENABLED",
        "LOKAY_AGENT",
        "LOKAY_MERGE_ENABLED",
        "LOKAY_REQUIRE_CHECKS",
        "LOKAY_CONFIG",
        "LOKAY_OFFLINE",
    ):
        monkeypatch.delenv(key, raising=False)

    cfg_path = tmp_path / "config.yaml"
    state = tmp_path / "state.jsonl"
    cfg_path.write_text(
        f"""
mode: live
github:
  assignee: t
repos:
  - name: o/r
    clone_path: {tmp_path}
executor:
  enabled: false
  agent: grok
  command: grok
limits:
  max_triage_per_tick: 3
  max_issues_per_tick: 0
  max_repairs_per_tick: 0
paths:
  state: {state}
merge:
  enabled: false
""",
        encoding="utf-8",
    )

    def boom(**_kwargs):
        raise RuntimeError("fala host exploded")

    monkeypatch.setattr(tick_mod, "run_path", boom)
    # This inventory test exercises Fala failure semantics, not host preflight.
    monkeypatch.setattr(tick_mod, "run_preflight", lambda *a, **k: {"ok": True})

    atom_calls: list[str] = []

    def fake_run(main_fn, argv):
        name = getattr(main_fn, "__module__", "") or ""
        atom_calls.append(name)
        if name.endswith("list_inbox"):
            return {
                "ok": True,
                "issues": [{"number": 42, "title": "x", "labels": []}],
            }
        if name.endswith("list_issues"):
            return {"ok": True, "issues": []}
        if name.endswith("list_prs"):
            return {"ok": True, "prs": []}
        if "triage" in name:
            return {"ok": True, "applied": True, "decision": {"decision": "ready"}}
        return {"ok": True}

    monkeypatch.setattr(tick_mod, "_run", fake_run)

    out = tick_mod.compose_tick(config_path=str(cfg_path), live=True)
    actions = out.get("actions") or []
    fala_fail = [
        a
        for a in actions
        if a.get("step") == "issue_triage" and a.get("ok") is False
    ]
    assert fala_fail, f"expected Fala fail action, got {actions!r}"
    assert "Fala path failed" in str(fala_fail[0].get("error") or "")
    triage_atoms = [n for n in atom_calls if "triage" in n]
    assert triage_atoms == [], f"atom triage must not run after Fala fail: {triage_atoms}"


def test_fallbacks_doc_exists():
    assert (ROOT / "docs" / "FALLBACKS.md").is_file()
    text = (ROOT / "docs" / "FALLBACKS.md").read_text(encoding="utf-8")
    assert "pr_checks_green" in text
    assert "Deleted" in text


def test_tick_fala_triage_noop_does_not_count_as_progress(tmp_path, monkeypatch):
    from lokay.compose import tick as tick_mod

    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"""
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
""", encoding="utf-8")

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
    monkeypatch.setattr(tick_mod, "run_path", lambda **kwargs: {
        "ok": True,
        "applied": False,
        "skipped": True,
        "decision": {"decision": "skip"},
    })
    out = tick_mod.compose_tick(config_path=str(cfg), live=True)
    assert out["progress"] == 0
    assert out["remaining"]["inbox"] == 1
