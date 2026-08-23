from pathlib import Path

import pytest

from lokay.graph_run import (
    _materialize_package,
    describe_package,
    find_default_package,
    normalize_path_result,
)


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
        "ready_hygiene",
        "plan_pass",
        "dispatch_triage",
        "resolve_conflicts",
        "closeout_prs",
        "reap_stale_implementing",
        "reap_over_budget",
        "refresh_occupancy",
        "reap_stale_worktrees",
        "select_implement",
        "queue_conflict",
        "dispatch_implement",
        "compute_health",
        "compact_state",
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
    assert "reap_stale_worktrees" in conduction["select_implement"]
    assert "refresh_occupancy" in conduction["reap_stale_worktrees"]
    assert "reap_over_budget" in conduction["refresh_occupancy"]
    assert "reap_stale_implementing" in conduction["reap_over_budget"]
    assert "closeout_prs" in conduction["reap_stale_implementing"]
    assert "select_implement" in conduction["queue_conflict"]
    assert "queue_conflict" in conduction["dispatch_implement"]
    assert "dispatch_implement" in conduction["compute_health"]
    assert "compute_health" in conduction["record_pass"]
    # Mega factory_tick / survey_repos / dispatch_closeout must not hide policy.
    assert "factory_tick" not in ids
    assert "survey_repos" not in ids
    assert "dispatch_closeout" not in ids


def test_factory_pass_injects_every_graph_atom(monkeypatch, tmp_path):
    """Fala runs every factory_pass atom; missing live injection is planned-only."""
    from lokay import graph_run

    captured = {}
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda config: None)

    def fake_host_run_package(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", fake_host_run_package)
    desc = describe_package()
    path = next(item for item in desc["paths"] if item["id"] == "factory_pass")
    ids = [node["id"] for node in path["nodes"]]
    graph_run.run_path(
        path_id="factory_pass",
        repo="mikolaj92/lokay",
        live=True,
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
    )
    injected = captured["effector_inputs"]
    assert set(injected) == set(ids)
    assert all(injected[step].get("live") is True for step in ids)
    assert injected["ready_hygiene"]["live"] is True


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
        lambda **kwargs: captured.update(
            token=__import__("os").environ["LOKAY_HEALTH_LEASE"]
        )
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


def test_every_subprocess_atom_inherits_pythonpath():
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    missing = [
        f"{path['id']}:{effector['id']}"
        for path in package["correlation_paths"]
        for effector in path["effectors"]
        if (effector.get("adapter") or {}).get("kind") == "subprocess"
        and (
            "PYTHONPATH"
            not in ((effector.get("adapter") or {}).get("inherit_env") or [])
            or "LOKAY_PROCESS_HEAD"
            not in ((effector.get("adapter") or {}).get("inherit_env") or [])
            or "LOKAY_HOST_FF_FETCHED"
            not in ((effector.get("adapter") or {}).get("inherit_env") or [])
        )
    ]
    assert missing == []


def test_parent_factory_inherits_fala_home_and_health_lease():
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    factory = next(
        path for path in package["correlation_paths"] if path["id"] == "factory_pass"
    )
    inherited = factory["effectors"][0]["adapter"]["inherit_env"]
    assert "FALA_HOME" in inherited
    assert "LOKAY_HEALTH_LEASE" in inherited
    assert "LOKAY_HEALTH_LEASE_PATH" in inherited
    assert "LOKAY_DISABLE_HEALTH_LEASE_ISSUE" in inherited
    assert "PYTHONPATH" in inherited
    assert "LOKAY_PROCESS_HEAD" in inherited
    assert "LOKAY_HOST_FF_FETCHED" in inherited


def test_subprocess_atoms_pin_project_cwd():
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    missing = [
        f"{path['id']}:{effector['id']}"
        for path in package["correlation_paths"]
        for effector in path["effectors"]
        if (effector.get("adapter") or {}).get("kind") == "subprocess"
        and (effector.get("adapter") or {}).get("cwd") != "PLACEHOLDER_PROJECT"
    ]
    assert missing == []


def _issue_delivery_path():
    return next(
        p for p in describe_package()["paths"] if p["id"] == "issue_to_pr_delivery"
    )


def test_describe_issue_to_pr_graph():
    desc = describe_package()
    gate = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    assert [n["id"] for n in gate["nodes"]] == [
        "get_issue",
        "resolve_implementation_issue",
        "collect_existing_delivery_pr",
        "collect_resumed_source",
        "resolve_existing_delivery",
        "issue_to_pr_subflow",
        "close_existing_delivery",
        "issue_to_pr_no_effect",
    ]
    ids = [n["id"] for n in _issue_delivery_path()["nodes"]]
    for required in (
        "plan_issue",
        "localize",
        "run_agent",
        "validate_coding_result",
        "select_coding_result",
        "finalize_coding_result",
        "pr_create",
    ):
        assert required in ids


def test_issue_to_pr_plan_issue_before_run_agent():
    by_id = {n["id"]: n for n in _issue_delivery_path()["nodes"]}
    assert "plan_issue" in by_id["localize"]["conduction"]
    assert {"plan_issue", "localize", "worktree_add"} <= set(
        by_id["run_agent"]["conduction"]
    )
    assert "run_agent" not in by_id["plan_issue"]["conduction"]


def test_issue_to_pr_routes_coding_and_test_decisions_in_fala():
    by_id = {n["id"]: n for n in _issue_delivery_path()["nodes"]}
    assert by_id["coding_retry_agent"]["when"] == {
        "upstream": "validate_coding_result",
        "path": "route",
        "equals": "retry",
    }
    assert by_id["evidence_coding_agent"]["when"] == {
        "upstream": "select_coding_result",
        "path": "route",
        "equals": "evidence",
    }
    assert by_id["repair_agent"]["when"] == {
        "upstream": "select_local_test",
        "path": "route",
        "equals": "fail",
    }
    assert by_id["push"]["when"] == {
        "upstream": "finalize_local_tests",
        "path": "route",
        "equals": "publish",
    }


def test_run_agent_timeouts_match_pi_budget():
    import tomllib

    raw = (
        Path(__file__).resolve().parents[1] / "fala" / "lokay.fala-package.toml"
    ).read_bytes()
    pkg = tomllib.loads(raw.decode())
    for path_id in ("issue_to_pr_delivery", "pr_repair"):
        path = next(p for p in pkg["correlation_paths"] if p["id"] == path_id)
        assert (
            int(
                next(n for n in path["effectors"] if n["id"] == "run_agent")["adapter"][
                    "timeout_seconds"
                ]
            )
            == 1800
        )
    delivery = next(
        p for p in pkg["correlation_paths"] if p["id"] == "issue_to_pr_delivery"
    )
    assert (
        int(
            next(n for n in delivery["effectors"] if n["id"] == "repair_agent")[
                "adapter"
            ]["timeout_seconds"]
        )
        == 1800
    )
    self_repair = next(p for p in pkg["correlation_paths"] if p["id"] == "self_repair")
    assert (
        int(
            next(
                n
                for n in self_repair["effectors"]
                if n["id"] == "self_repair_run_agent"
            )["adapter"]["timeout_seconds"]
        )
        == 1800
    )


def test_test_local_timeouts_are_bounded():
    """Every test_local effector uses the local-suite timeout budget."""
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    test_locals = [
        effector
        for path in package["correlation_paths"]
        for effector in path["effectors"]
        if effector["id"] == "test_local"
    ]
    assert test_locals
    assert all(
        int(effector["adapter"]["timeout_seconds"]) == 300 for effector in test_locals
    )


def test_describe_includes_pr_repair():
    path = next(p for p in describe_package()["paths"] if p["id"] == "pr_repair")
    by_id = {node["id"]: node for node in path["nodes"]}
    assert "rebase_onto_base" not in by_id
    assert "commit_initial_repair" in by_id["test_local"]["conduction"]
    assert by_id["pr_repair_retry_agent"]["when"]["equals"] == "retry"
    assert by_id["evidence_repair_agent"]["when"]["equals"] == "evidence"
    assert by_id["pr_test_repair_agent"]["when"]["equals"] == "fail"
    assert by_id["push"]["when"]["equals"] == "publish"
    assert "assert_real_diff" in by_id["push"]["conduction"]


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
    return normalize_path_result(
        {
            "ok": ok,
            "path_id": path_id,
            "live": live,
            "fala": {"processes": processes, "effector_results": results},
        }
    )


def test_fala_approve_contract():
    out = _host(
        "pr_triage",
        {
            "publish_pr_review": {
                "id": "publish_pr_review",
                "status": "completed",
                "output": {"values": {"decision": {"verdict": "approve"}}},
            },
            "pr_merge": {
                "id": "pr_merge",
                "status": "completed",
                "output": {"values": {"merged": True}},
            },
            "close_issue": {
                "id": "close_issue",
                "status": "completed",
                "output": {"values": {"issue": 33}},
            },
        },
    )
    assert out["ok"] and out["merged"] and out["closed_issue"] == 33


def test_fala_request_changes_contract():
    review = {"verdict": "request_changes", "secrets": False, "blocking": ["test"]}
    out = _host(
        "pr_triage",
        {
            "publish_pr_review": {
                "id": "publish_pr_review",
                "status": "completed",
                "output": {"values": {"decision": review}},
            },
            "review_repair_gate": {
                "id": "review_repair_gate",
                "status": "completed",
                "output": {"values": {"route": "repair"}},
            },
            "pr_repair_subflow": {
                "id": "pr_repair_subflow",
                "status": "completed",
                "output": {"values": {"ok": True, "kind": "pr_repair"}},
            },
        },
    )
    assert out["skipped"] and out["repaired"] and out["review"] == review


def test_fala_already_reviewed_request_changes_still_enters_repair():
    out = _host(
        "pr_triage",
        {
            "publish_pr_review": {
                "id": "publish_pr_review",
                "status": "completed",
                "output": {
                    "values": {
                        "skipped": True,
                        "reason": "already_reviewed_head",
                        "decision": {"verdict": "request_changes"},
                    }
                },
            },
            "review_repair_gate": {
                "id": "review_repair_gate",
                "status": "completed",
                "output": {"values": {"route": "repair"}},
            },
            "pr_repair_subflow": {
                "id": "pr_repair_subflow",
                "status": "completed",
                "output": {"values": {"ok": True}},
            },
        },
    )
    assert out["skipped"] is True
    assert out["repaired"] is True
    assert out["review"]["verdict"] == "request_changes"


def test_fala_needs_human_contract():
    out = _host(
        "pr_triage",
        {
            "publish_pr_review": {
                "id": "publish_pr_review",
                "status": "completed",
                "output": {"values": {"decision": {"verdict": "needs_human"}}},
            },
            "review_manual": {
                "id": "review_manual",
                "status": "completed",
                "output": {
                    "values": {"terminal": True, "reason": "review_needs_human"}
                },
            },
        },
    )
    assert out["skipped"] and not out["repairable"] and out["needs_review"]


def test_self_repair_graph_orders_direct_main_recovery():
    package = describe_package()
    path = next(item for item in package["paths"] if item["id"] == "self_repair")
    conduction = {node["id"]: node["conduction"] for node in path["nodes"]}
    assert conduction == {
        "self_repair_prepare": [],
        "self_repair_run_agent": ["self_repair_prepare"],
        "self_repair_validate": ["self_repair_prepare", "self_repair_commit"],
        "self_repair_commit": ["self_repair_prepare", "self_repair_run_agent"],
        "self_repair_push_main": [
            "self_repair_prepare",
            "self_repair_validate",
            "self_repair_commit",
        ],
        "self_repair_activate": ["self_repair_push_main"],
        "self_repair_preflight": ["self_repair_activate"],
        "self_repair_close": ["self_repair_preflight"],
    }
    assert not any(
        node in {"pr_create", "pr_review", "pr_merge", "pr_repair"}
        for node in conduction
    )


def test_fala_issue_to_pr_no_pr_is_fail_closed():
    out = _host(
        "issue_to_pr",
        {
            "make_branch": {
                "id": "make_branch",
                "status": "completed",
                "output": {"values": {"branch": "lokay/x"}},
            },
            "pr_label": {
                "id": "pr_label",
                "status": "completed",
                "output": {"values": {"pr": None}},
            },
        },
    )
    assert out["ok"] is False
    assert out["error"] == "issue_to_pr produced no PR"
    assert out["reason"] == "no_pr"


def test_fala_issue_to_pr_with_pr_ok():
    out = _host(
        "issue_to_pr",
        {
            "make_branch": {
                "id": "make_branch",
                "status": "completed",
                "output": {"values": {"branch": "lokay/x"}},
            },
            "pr_create": {
                "id": "pr_create",
                "status": "completed",
                "output": {"values": {"pr": 12}},
            },
            "pr_label": {
                "id": "pr_label",
                "status": "completed",
                "output": {"values": {"pr": 12}},
            },
        },
    )
    assert out["ok"] is True
    assert out["pr"] == 12


def test_fala_zero_diff_repair_contract():
    out = _host(
        "pr_repair",
        {
            "commit_all": {
                "id": "commit_all",
                "status": "completed",
                "output": {"values": {"committed": False}},
            }
        },
    )
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
    out = normalize_path_result(
        {
            "ok": True,
            "path_id": "pr_triage",
            "fala": {"processes": [{"id": "pr_review", "status": "completed"}]},
        }
    )
    assert out["ok"] is False
    assert "effector_results" in out["error"]


def test_malformed_effector_results_fails_closed():
    out = normalize_path_result(
        {
            "ok": True,
            "path_id": "pr_triage",
            "fala": {"effector_results": {"pr_review": "not an entry"}},
        }
    )
    assert out["ok"] is False
    assert "malformed" in out["error"]


def test_completed_effector_without_output_fails_closed():
    out = normalize_path_result(
        {
            "ok": True,
            "path_id": "pr_triage",
            "fala": {
                "effector_results": {
                    "pr_review": {
                        "id": "pr_review",
                        "status": "completed",
                        "output": None,
                    }
                }
            },
        }
    )
    assert out["ok"] is False
    assert "without structured output" in out["error"]


def test_fala_review_not_required_contract_allows_merge():
    out = _host(
        "pr_triage",
        {
            "publish_pr_review": {
                "id": "publish_pr_review",
                "status": "completed",
                "output": {
                    "values": {
                        "skipped": True,
                        "reason": "llm_review_not_required",
                        "decision": {"verdict": "approve"},
                        "merge_ok": True,
                    }
                },
            },
            "pr_merge": {
                "id": "pr_merge",
                "status": "completed",
                "output": {"values": {"merged": True}},
            },
        },
    )
    assert out["ok"] is True
    assert out["merged"] is True
    assert not out.get("skipped")


def test_fala_issue_triage_applied_contract():
    out = _host(
        "issue_triage",
        {
            "finalize_issue_triage": {
                "id": "finalize_issue_triage",
                "status": "completed",
                "output": {"values": {"decision": {"verdict": "ready"}}},
            },
            "apply_issue_ready": {
                "id": "apply_issue_ready",
                "status": "completed",
                "output": {"values": {"applied": True}},
            },
        },
    )
    assert out["ok"] and out["applied"] and not out["skipped"]
    assert out["implementable"] is True


def test_fala_issue_triage_skip_contract_is_not_applied():
    out = _host(
        "issue_triage",
        {
            "finalize_issue_triage": {
                "id": "finalize_issue_triage",
                "status": "completed",
                "output": {"values": {"decision": {"verdict": "skip"}}},
            },
        },
    )
    assert out["ok"] and not out["applied"] and out["skipped"]


def test_run_path_scopes_inputs_to_authored_fala_path(tmp_path, monkeypatch):
    import lokay.graph_run as graph_run
    import tomllib

    package = Path(__file__).resolve().parents[1] / "fala" / "lokay.fala-package.toml"
    authored = {
        path["id"]: {node["id"] for node in path["effectors"]}
        for path in tomllib.loads(package.read_text())["correlation_paths"]
    }
    captured = []

    def fake_host_run_package(**kwargs):
        captured.append(kwargs)
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", fake_host_run_package)
    for path_id, effectors in authored.items():
        graph_run.run_path(
            path_id=path_id,
            repo="a/b",
            issue=1,
            pr=2,
            branch="ai/fix/1-x",
            live=False,
            package_path=str(package),
            db_path=str(tmp_path / path_id),
        )
        assert set(captured[-1]["effector_inputs"]) == effectors


def test_factory_path_lifts_host_updated_from_failed_begin():
    out = _host(
        "factory_pass",
        {
            "host_ff": {
                "id": "host_ff",
                "status": "completed",
                "output": {"values": {"ok": True, "updated": True, "head": "abc"}},
            },
            "factory_begin": {
                "id": "factory_begin",
                "status": "failed",
                "error": '{"ok": false, "reason": "host_updated", "health": "host_updated"}',
            },
        },
        ok=False,
    )
    assert out["ok"] is False
    assert out["reason"] == "host_updated"
    assert out["health"] == "host_updated"
    assert out["restart_required"] is True


def test_factory_path_normalizes_tick_contract():
    out = _host(
        "factory_pass",
        {
            "record_pass": {
                "id": "record_pass",
                "status": "completed",
                "output": {
                    "values": {
                        "ok": True,
                        "tick": {
                            "ok": True,
                            "health": "progress",
                            "progress": 1,
                            "remaining": {"ready": 2},
                        },
                    }
                },
            },
        },
    )
    assert out["ok"] is True
    assert out["health"] == "progress"
    assert out["progress"] == 1
    assert out["remaining"] == {"ready": 2}


def test_factory_path_normalizes_legacy_factory_tick_contract():
    out = _host(
        "factory_pass",
        {
            "factory_tick": {
                "id": "factory_tick",
                "status": "completed",
                "output": {
                    "values": {
                        "ok": True,
                        "tick": {
                            "ok": False,
                            "health": "stall",
                            "progress": 0,
                            "error": "stall: actionable work remains but no progress this pass",
                        },
                    }
                },
            },
        },
    )
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
        graph_run.run_path(
            path_id="missing",
            repo="a/b",
            live=False,
            package_path=str(package),
            db_path=str(tmp_path / "missing"),
        )
    assert called is False


def test_pr_review_outcome_is_routed_by_fala_conditions():
    package = describe_package()
    path = next(item for item in package["paths"] if item["id"] == "pr_triage")
    by_id = {node["id"]: node for node in path["nodes"]}
    assert by_id["pr_repair_subflow"]["when"] == {
        "upstream": "review_repair_gate",
        "path": "route",
        "equals": "repair",
    }
    assert by_id["review_manual"]["when"] == {
        "upstream": "publish_pr_review",
        "path": "decision.verdict",
        "equals": "needs_human",
    }
    for node_id in (
        "worktree_add",
        "test_local",
        "pr_merge",
        "stage_clear",
        "close_issue",
    ):
        assert by_id[node_id]["when"] == {
            "upstream": "publish_pr_review",
            "path": "decision.verdict",
            "equals": "approve",
        }
