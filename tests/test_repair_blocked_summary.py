"""A blocked repair is not a successful not-applicable repair."""
from pathlib import Path
import tomllib

import pytest

from lokay.organ.repair_boundary import handle_repair_boundary


@pytest.mark.parametrize("reason", ["repair_start_identity_missing", "repair_start_head_mismatch", "fork_hosted_repair_unsupported"])
def test_authored_summary_retains_worktree_blocker(monkeypatch, reason):
    monkeypatch.setattr("lokay.organ.repair_boundary.load_config", lambda _: object())
    package = tomllib.loads((Path(__file__).parents[1] / "fala/lokay.fala-package.toml").read_text())
    graph = next(p for p in package["correlation_paths"] if p["id"] == "pr_repair")
    node = next(n for n in graph["effectors"] if n["id"] == "summarize_pr_repair")
    available = {
        "admit_pr_repair": {"route": "open"},
        "worktree_add": {"ok": True, "route": "missing", "reason": reason},
        "finalize_repair_tests": {"route": "not_applicable"},
    }
    out = handle_repair_boundary(
        "summarize_pr_repair",
        {"branch": "ai/fix/17-docs", "repair_kind": "review", "head_sha": "a" * 40},
        {key: available.get(key, {}) for key in node["conduction"]},
        {"repo": "o/r", "pr_number": 34},
    )
    assert out["result"]["ok"] is False
    assert out["result"]["terminal"] == "blocked"
    assert out["result"]["reason"] == reason
    assert out["result"]["head_sha"] == "a" * 40
    assert out["result"]["repaired"] is False
    assert out["result"]["published"] is False
    from lokay.fala_organ import organ_envelope
    from lokay.graph_run import normalize_path_result

    terminal = organ_envelope("summarize_pr_repair", out)
    normalized = normalize_path_result({
        "ok": True, "path_id": "pr_repair", "fala": {"effector_results": {
            "summarize_pr_repair": {"status": "succeeded", "output": {"payload": terminal}},
        }},
    })
    assert normalized["ok"] is False
    assert normalized["reason"] == reason
    assert normalized["terminal"] == "blocked"


def test_native_fala_carries_blocked_summary_to_parent(tmp_path):
    from test_issue_triage_fala import base_effector, run_graph
    from lokay.graph_run import normalize_path_result

    body = base_effector('''
if a == 'admit_pr_repair': v.update(route='open')
if a == 'worktree_add': v.update(route='missing', reason='repair_start_identity_missing')
if a in {'select_evidence_repair', 'select_repair_test', 'select_test_repair_result', 'select_repair_test_recheck', 'finalize_repair_tests'}: v.update(route='not_applicable')
if a == 'summarize_pr_repair':
    from lokay.fala_organ import _conduction_values, organ_envelope
    from lokay.organ.repair_boundary import handle_repair_boundary
    v = organ_envelope(a, handle_repair_boundary(a,
        {'branch': 'ai/fix/17-docs', 'repair_kind': 'review', 'head_sha': 'a' * 40},
        _conduction_values(m), {'repo': 'o/r', 'pr_number': 34}))
''')
    result = run_graph(tmp_path, body, "blocked-summary", path_id="pr_repair")
    assert result["run_status"] == "completed"
    assert result["effector_results"]["run_agent"]["status"] == "skipped"
    assert result["effector_results"]["push"]["status"] == "skipped"
    out = normalize_path_result({"ok": True, "path_id": "pr_repair", "fala": result})
    assert out["ok"] is False
    assert out["terminal"] == "blocked"
    assert out["reason"] == "repair_start_identity_missing"


@pytest.mark.parametrize("live", [False, True])
def test_parent_retains_blocked_reason_without_spending_attempt(monkeypatch, tmp_path, live):
    from lokay.proc import run_parent_pr_repair_subflow as parent

    monkeypatch.setattr(parent.pr_repair_receipts, "resolve_state_dir", lambda _: tmp_path)
    monkeypatch.setattr(parent.pr_repair_receipts, "resolve_budget", lambda _: 2)
    monkeypatch.setattr(parent, "_review_task_is_current", lambda *a, **kw: True)
    monkeypatch.setattr(parent, "compose_pr_repair", lambda **kw: {
        "ok": False, "terminal": "blocked", "reason": "repair_start_identity_missing",
        "repo": "o/r", "pr": 34, "branch": "ai/fix/17-docs",
        "head_sha": "a" * 40, "repaired": False, "published": False,
    })
    out = parent.run({"repo": "o/r", "pr": 34, "branch": "ai/fix/17-docs", "repair_kind": "review"}, config_path=None, live=live)
    assert out["route"] == "fail_closed"
    assert out["reason"] == "repair_start_identity_missing"
    assert out["attempts"] == 0
