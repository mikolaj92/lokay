from pathlib import Path

import pytest

from lokay.graph_run import _materialize_package, describe_package, find_default_package, normalize_path_result


def test_describe_parent_factory_graph():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    assert [node["id"] for node in path["nodes"]] == ["factory_tick"]


def test_describe_issue_to_pr_graph():
    desc = describe_package()
    assert desc["package_id"] == "lokay"
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    ids = [n["id"] for n in path["nodes"]]
    assert ids[0] == "get_issue"
    assert "run_agent" in ids
    assert "pr_create" in ids
    # agent depends on worktree
    agent = next(n for n in path["nodes"] if n["id"] == "run_agent")
    assert "worktree_add" in agent["conduction"]
    assert "get_issue" in agent["conduction"]


def test_describe_includes_pr_repair():
    desc = describe_package()
    assert any(p["id"] == "pr_repair" for p in desc["paths"])


def test_package_file_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "fala" / "lokay.fala-package.toml").is_file()


def test_package_uses_uv_and_project_placeholder_only():
    """Canonical path: hardcode uv + PLACEHOLDER_PROJECT; no PLACEHOLDER_PYTHON."""
    pkg = find_default_package()
    text = pkg.read_text(encoding="utf-8")
    assert "PLACEHOLDER_PROJECT" in text
    assert "PLACEHOLDER_PYTHON" not in text
    assert '"uv", "run", "--project", "PLACEHOLDER_PROJECT"' in text


def test_materialize_package_substitutes_project_only(tmp_path: Path):
    """Single modern substitution — no silent rewrite of legacy tokens."""
    src = tmp_path / "pkg.toml"
    src.write_text(
        'command = ["uv", "run", "--project", "PLACEHOLDER_PROJECT", "python"]\n'
        'stale = "PLACEHOLDER_PYTHON"\n',
        encoding="utf-8",
    )
    dest = tmp_path / "out.toml"
    project = tmp_path / "checkout"
    project.mkdir()
    _materialize_package(src, dest, project=project)
    out = dest.read_text(encoding="utf-8")
    resolved = str(project.resolve())
    assert resolved in out
    assert "PLACEHOLDER_PROJECT" not in out
    # leftover legacy token is not silently rewritten to "uv"
    assert "PLACEHOLDER_PYTHON" in out
    assert '["uv", "run", "--project",' in out


def _host(path_id, results, *, live=True, ok=True):
    # Exact Fala #156 host result: process summaries are metadata-only; decoded
    # terminal outputs live in the mapping keyed by authored effector id.
    processes = [
        {"id": value.get("id", key), "status": value.get("status")}
        for key, value in results.items()
    ]
    return normalize_path_result({
        "ok": ok,
        "path_id": path_id,
        "live": live,
        "fala": {"processes": processes, "effector_results": results},
    })


def test_fala_approve_contract():
    out = _host("pr_triage", {
        "pr_review": {"id": "pr_review", "status": "completed", "output": {"values": {"decision": {"verdict": "approve"}}}},
        "pr_merge": {"id": "pr_merge", "status": "completed", "output": {"values": {"merged": True}}},
        "close_issue": {"id": "close_issue", "status": "completed", "output": {"values": {"issue": 33}}},
    })
    assert out["ok"] and out["merged"] and out["closed_issue"] == 33


def test_fala_request_changes_contract():
    review = {"verdict": "request_changes", "secrets": False, "blocking": ["test"]}
    out = _host("pr_triage", {"pr_review": {"id": "pr_review", "status": "completed", "output": {"values": {"decision": review}}}})
    assert out["skipped"] and out["repairable"] and out["review"] == review


def test_fala_needs_human_contract():
    out = _host("pr_triage", {
        "pr_review": {
            "id": "pr_review",
            "status": "completed",
            "output": {"values": {"decision": {"verdict": "needs_human"}}},
        }
    })
    assert out["skipped"] and not out["repairable"]


def test_fala_zero_diff_repair_contract():
    out = _host("pr_repair", {"commit_all": {"id": "commit_all", "status": "completed", "output": {"values": {"committed": False}}}})
    assert out["ok"] is False and out["error"] == "repair produced no commit"


def test_completed_path_without_effector_results_fails_closed():
    out = normalize_path_result({
        "ok": True,
        "path_id": "pr_triage",
        "fala": {"processes": [{"id": "pr_review", "status": "completed"}]},
    })
    assert out["ok"] is False
    assert "effector_results" in out["error"]


def test_malformed_effector_results_fails_closed():
    out = normalize_path_result({
        "ok": True,
        "path_id": "pr_triage",
        "fala": {"effector_results": {"pr_review": "not an entry"}},
    })
    assert out["ok"] is False
    assert "malformed" in out["error"]


def test_completed_effector_without_output_fails_closed():
    out = normalize_path_result({
        "ok": True,
        "path_id": "pr_triage",
        "fala": {"effector_results": {"pr_review": {"id": "pr_review", "status": "completed", "output": None}}},
    })
    assert out["ok"] is False
    assert "without structured output" in out["error"]


def test_fala_review_not_required_contract_allows_merge():
    out = _host("pr_triage", {
        "pr_review": {"id": "pr_review", "status": "completed", "output": {"values": {"skipped": True, "reason": "llm_review_not_required", "merge_ok": True}}},
        "pr_merge": {"id": "pr_merge", "status": "completed", "output": {"values": {"merged": True}}},
    })
    assert out["ok"] is True
    assert out["merged"] is True
    assert not out.get("skipped")


def test_fala_issue_triage_applied_contract():
    out = _host("issue_triage", {
        "triage_issue": {"id": "triage_issue", "status": "completed", "output": {"values": {"applied": True, "decision": {"decision": "ready"}}}},
    })
    assert out["ok"] and out["applied"] and not out["skipped"]


def test_fala_issue_triage_skip_contract_is_not_applied():
    out = _host("issue_triage", {
        "triage_issue": {"id": "triage_issue", "status": "completed", "output": {"values": {"applied": False, "decision": {"decision": "skip"}}}},
    })
    assert out["ok"] and not out["applied"] and out["skipped"]


def test_run_path_scopes_inputs_to_selected_fala_path(tmp_path, monkeypatch):
    import lokay.graph_run as graph_run

    package = Path(__file__).resolve().parents[1] / "fala" / "lokay.fala-package.toml"
    captured = []

    def fake_host_run_package(**kwargs):
        captured.append(kwargs)
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", fake_host_run_package)
    expected = {
        "factory_pass": {"factory_tick"},
        "issue_to_pr": {"get_issue", "assign_issue", "make_branch", "worktree_add", "run_agent", "commit_all", "push", "pr_create", "list_prs", "pr_label"},
        "issue_triage": {"get_issue", "triage_issue"},
        "pr_repair": {"pr_checks", "worktree_add", "run_agent", "commit_all", "push"},
        "pr_triage": {"pr_checks", "pr_review", "pr_merge", "close_issue"},
    }
    for path_id, effectors in expected.items():
        graph_run.run_path(path_id=path_id, repo="a/b", issue=1, pr=2, branch="ai/fix/1-x", live=False, package_path=str(package), db_path=str(tmp_path / path_id))
        assert set(captured[-1]["effector_inputs"]) == effectors


def test_factory_path_normalizes_tick_contract():
    out = _host("factory_pass", {
        "factory_tick": {
            "id": "factory_tick",
            "status": "completed",
            "output": {"values": {
                "ok": True,
                "tick": {
                    "ok": True,
                    "health": "progress",
                    "progress": 1,
                    "remaining": {"ready": 2},
                },
            }},
        },
    })
    assert out["ok"] is True
    assert out["health"] == "progress"
    assert out["progress"] == 1
    assert out["remaining"] == {"ready": 2}


def test_run_path_rejects_unknown_path_before_fala(tmp_path, monkeypatch):
    import lokay.graph_run as graph_run

    called = False
    def fake_host_run_package(**kwargs):
        nonlocal called
        called = True
        return {}
    monkeypatch.setattr("fala.host_run_package", fake_host_run_package)
    package = Path(__file__).resolve().parents[1] / "fala" / "lokay.fala-package.toml"
    with pytest.raises(ValueError, match="unknown Fala correlation path"):
        graph_run.run_path(path_id="missing", repo="a/b", live=False, package_path=str(package), db_path=str(tmp_path / "missing"))
    assert called is False
