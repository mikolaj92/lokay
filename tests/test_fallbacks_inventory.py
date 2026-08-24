"""Issue #19: rare super-fallbacks deleted or promoted — no zombie shims."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from lokay import gh_prs, graph_run

ROOT = Path(__file__).resolve().parents[1]


def _run_inbox(module, pass_dir):
    from lokay.passkit import io as pass_io

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    issues = {}
    for repo in begin.get("repos") or []:
        out = module._run(module.p_list_inbox.main, ["--repo", repo])
        rows = list(out.get("issues") or []) if out.get("ok") else []
        by[repo] = len(rows)
        issues[repo] = rows
    working.update(
        inbox_by_repo=by,
        inbox_issues_by_repo=issues,
        remaining_inbox=sum(by.values()),
        inbox_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_pr_survey(module, pass_dir):
    from lokay.passkit import io as pass_io
    from lokay.passkit.support import is_manual_pr

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    for repo in begin.get("repos") or []:
        out = module._run(module.p_list_prs.main, ["--repo", repo])
        by[repo] = list(out.get("prs") or []) if out.get("ok") else []
    working.update(
        prs_by_repo=by,
        remaining_prs=sum(len(v) for v in by.values()),
        actionable_prs=sum(not is_manual_pr(x) for v in by.values() for x in v),
        manual_prs=sum(is_manual_pr(x) for v in by.values() for x in v),
        pr_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


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
