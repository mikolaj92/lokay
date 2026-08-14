from pathlib import Path

import pytest

from lokay.graph_run import _materialize_package, describe_package, find_default_package, normalize_path_result


def test_describe_parent_factory_graph():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "host_ff",
        "factory_begin",
        "survey_prs",
        "survey_inbox",
        "survey_ready",
        "plan_pass",
        "dispatch_triage",
        "resolve_conflicts",
        "closeout_prs",
        "select_implement",
        "queue_conflict",
        "dispatch_implement",
        "compute_health",
        "record_pass",
    ]
    conduction = {node["id"]: node["conduction"] for node in path["nodes"]}
    assert conduction["factory_begin"] == ["host_ff"]
    assert conduction["survey_prs"] == ["factory_begin"]
    assert "survey_prs" in conduction["survey_inbox"]
    assert "survey_inbox" in conduction["survey_ready"]
    assert "survey_ready" in conduction["plan_pass"]
    assert "plan_pass" in conduction["dispatch_triage"]
    assert "dispatch_triage" in conduction["resolve_conflicts"]
    assert "resolve_conflicts" in conduction["closeout_prs"]
    assert "closeout_prs" in conduction["select_implement"]
    assert "select_implement" in conduction["queue_conflict"]
    assert "queue_conflict" in conduction["dispatch_implement"]
    assert "dispatch_implement" in conduction["compute_health"]
    assert "compute_health" in conduction["record_pass"]
    # Mega factory_tick / survey_repos / dispatch_closeout must not hide policy.
    assert "factory_tick" not in ids
    assert "survey_repos" not in ids
    assert "dispatch_closeout" not in ids


def test_run_path_preserves_parent_health_token(monkeypatch, tmp_path):
    from lokay import graph_run

    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "parent-token")
    monkeypatch.setattr(
        "lokay.preflight.require_healthy",
        lambda config: monkeypatch.setenv("LOKAY_HEALTH_LEASE", "nested-token"),
    )
    captured = {}
    monkeypatch.setattr(
        "fala.host_run_package",
        lambda **kwargs: captured.update(token=__import__("os").environ["LOKAY_HEALTH_LEASE"])
        or {"ok": True, "run_status": "completed", "effector_results": {}},
    )

    graph_run.run_path(
        path_id="factory_pass",
        repo="__factory__",
        live=True,
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
    )

    assert captured["token"] == "parent-token"


def test_parent_factory_inherits_fala_home_and_health_lease():
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    factory = next(path for path in package["correlation_paths"] if path["id"] == "factory_pass")
    inherited = factory["effectors"][0]["adapter"]["inherit_env"]
    assert "FALA_HOME" in inherited
    assert "LOKAY_HEALTH_LEASE" in inherited
    assert "LOKAY_HEALTH_LEASE_PATH" in inherited
    assert "LOKAY_DISABLE_HEALTH_LEASE_ISSUE" in inherited


def test_describe_issue_to_pr_graph():
    desc = describe_package()
    assert desc["package_id"] == "lokay"
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    ids = [n["id"] for n in path["nodes"]]
    assert ids[0] == "get_issue"
    assert "run_agent" in ids
    assert "plan_issue" in ids
    assert "localize" in ids
    assert "pr_create" in ids
    assert "stage_implementing" in ids
    assert "stage_pr_open" in ids
    # plan before localize before agent; agent depends on plan + localize + worktree
    plan = next(n for n in path["nodes"] if n["id"] == "plan_issue")
    assert "worktree_add" in plan["conduction"]
    assert "get_issue" in plan["conduction"]
    localize = next(n for n in path["nodes"] if n["id"] == "localize")
    assert "plan_issue" in localize["conduction"]
    assert "worktree_add" in localize["conduction"]
    agent = next(n for n in path["nodes"] if n["id"] == "run_agent")
    assert "worktree_add" in agent["conduction"]
    assert "plan_issue" in agent["conduction"]
    assert "localize" in agent["conduction"]
    assert "get_issue" in agent["conduction"]
    worktree = next(n for n in path["nodes"] if n["id"] == "worktree_add")
    assert "stage_implementing" in worktree["conduction"]
    pr_open = next(n for n in path["nodes"] if n["id"] == "stage_pr_open")
    assert "pr_create" in pr_open["conduction"]
    repair = next(n for n in path["nodes"] if n["id"] == "repair_agent")
    assert "test_local" in repair["conduction"]
    recheck = next(n for n in path["nodes"] if n["id"] == "test_local_recheck")
    assert "repair_agent" in recheck["conduction"]
    push = next(n for n in path["nodes"] if n["id"] == "push")
    assert "test_local_recheck" in push["conduction"]
    assert "assert_real_diff" in push["conduction"]


def test_issue_to_pr_plan_issue_before_run_agent():
    """Serial evidence path: worktree_add → plan_issue → localize → run_agent."""
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "plan_issue" in by_id
    assert "localize" in by_id
    assert "plan_issue" in by_id["run_agent"]["conduction"]
    assert "localize" in by_id["run_agent"]["conduction"]
    assert "plan_issue" in by_id["localize"]["conduction"]
    assert "worktree_add" in by_id["plan_issue"]["conduction"]
    # plan_issue / localize must not depend on run_agent (ordering before agent)
    assert "run_agent" not in by_id["plan_issue"]["conduction"]
    assert "run_agent" not in by_id["localize"]["conduction"]


def test_issue_to_pr_commit_then_test_then_assert_is_a_dag():
    """commit_all must not wait on assert_real_diff (that cycle never reaches push)."""
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "run_agent" in by_id["commit_all"]["conduction"]
    assert "assert_real_diff" not in by_id["commit_all"]["conduction"]
    assert "commit_all" in by_id["test_local"]["conduction"]
    assert "test_local" in by_id["assert_real_diff"]["conduction"]
    assert "assert_real_diff" in by_id["push"]["conduction"]


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


def test_self_repair_graph_orders_direct_main_recovery():
    package = describe_package()
    path = next(item for item in package["paths"] if item["id"] == "self_repair")
    conduction = {node["id"]: node["conduction"] for node in path["nodes"]}
    assert conduction == {
        "self_repair_prepare": [],
        "self_repair_run_agent": ["self_repair_prepare"],
        "self_repair_validate": ["self_repair_prepare", "self_repair_run_agent"],
        "self_repair_commit": ["self_repair_prepare", "self_repair_validate"],
        "self_repair_push_main": ["self_repair_prepare", "self_repair_validate", "self_repair_commit"],
        "self_repair_activate": ["self_repair_push_main"],
        "self_repair_preflight": ["self_repair_activate"],
        "self_repair_close": ["self_repair_preflight"],
    }
    assert not any(node in {"pr_create", "pr_review", "pr_merge", "pr_repair"} for node in conduction)


def test_fala_zero_diff_repair_contract():
    out = _host("pr_repair", {"commit_all": {"id": "commit_all", "status": "completed", "output": {"values": {"committed": False}}}})
    assert out["ok"] is False and out["error"] == "repair produced no commit"


def test_fala_agent_committed_repair_contract():
    out = _host(
        "pr_repair",
        {
            "commit_all": {
                "id": "commit_all",
                "status": "completed",
                "output": {"values": {"committed": False}},
            },
            "push": {
                "id": "push",
                "status": "completed",
                "output": {"values": {"ok": True, "planned": False}},
            },
        },
    )
    assert out["ok"] is True


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
        "intake_issue": {"id": "intake_issue", "status": "completed", "output": {"values": {"applied": False, "implementable": True, "decision": {"decision": "ready"}, "skipped": False}}},
    })
    assert out["ok"] and out["applied"] and not out["skipped"]
    assert out["implementable"] is True


def test_fala_issue_triage_skip_contract_is_not_applied():
    out = _host("issue_triage", {
        "triage_issue": {"id": "triage_issue", "status": "completed", "output": {"values": {"applied": False, "decision": {"decision": "skip"}}}},
        "intake_issue": {"id": "intake_issue", "status": "completed", "output": {"values": {"applied": False, "implementable": False, "decision": {"decision": "skip"}, "skipped": True}}},
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
        "factory_pass": {
            "host_ff",
            "factory_begin",
            "survey_prs",
            "survey_inbox",
            "survey_ready",
            "plan_pass",
            "dispatch_triage",
            "resolve_conflicts",
            "closeout_prs",
            "select_implement",
            "queue_conflict",
            "dispatch_implement",
            "compute_health",
            "record_pass",
        },
        "issue_to_pr": {
            "get_issue", "assign_issue", "stage_implementing", "make_branch",
            "worktree_add", "plan_issue", "localize", "cycle_start", "run_agent",
            "commit_all", "test_local", "repair_agent", "test_local_recheck",
            "assert_real_diff", "push", "pr_create", "cycle_end", "stage_pr_open",
            "list_prs", "pr_label",
        },
        "issue_triage": {"get_issue", "triage_issue", "intake_issue", "issue_split"},
        "pr_repair": {
            "pr_checks", "stage_repairing", "worktree_add", "localize", "run_agent",
            "commit_all", "test_local", "assert_real_diff", "push",
        },
        "pr_triage": {
            "pr_checks", "pr_review", "worktree_add", "test_local",
            "pr_merge", "stage_clear", "close_issue",
        },
    }
    for path_id, effectors in expected.items():
        graph_run.run_path(path_id=path_id, repo="a/b", issue=1, pr=2, branch="ai/fix/1-x", live=False, package_path=str(package), db_path=str(tmp_path / path_id))
        assert set(captured[-1]["effector_inputs"]) == effectors


def test_factory_path_normalizes_tick_contract():
    out = _host("factory_pass", {
        "record_pass": {
            "id": "record_pass",
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


def test_factory_path_normalizes_legacy_factory_tick_contract():
    out = _host("factory_pass", {
        "factory_tick": {
            "id": "factory_tick",
            "status": "completed",
            "output": {"values": {
                "ok": True,
                "tick": {
                    "ok": False,
                    "health": "stall",
                    "progress": 0,
                    "error": "stall: actionable work remains but no progress this pass",
                },
            }},
        },
    })
    assert out["ok"] is False
    assert out["health"] == "stall"


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
