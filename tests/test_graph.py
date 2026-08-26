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
        "self_repair",
        "pr_triage",
        "stale_worktree_reap",
        "issue_triage",
        "select_next_issue",
        "issue_to_pr",
        "pr_triage_after",
        "record_pass",
        "factory_pass_terminal",
    ]
    conduction = {node["id"]: node["conduction"] for node in path["nodes"]}
    assert conduction["pr_triage"] == ["self_repair"]
    assert "self_repair" in conduction["stale_worktree_reap"]
    assert "pr_triage" in conduction["stale_worktree_reap"]
    assert "stale_worktree_reap" in conduction["issue_triage"]
    assert "issue_triage" in conduction["select_next_issue"]
    assert "issue_triage" in conduction["issue_to_pr"]
    assert "issue_to_pr" in conduction["pr_triage_after"]
    assert "issue_triage" in conduction["record_pass"]
    assert "issue_to_pr" in conduction["record_pass"]
    assert "pr_triage_after" in conduction["record_pass"]
    assert conduction["factory_pass_terminal"] == ["record_pass"]
    # Mega factory_tick / survey_repos / dispatch_closeout must not hide policy.
    assert "factory_tick" not in ids
    assert "survey_repos" not in ids
    assert "dispatch_closeout" not in ids


def test_ready_hygiene_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "ready_hygiene")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_ready_hygiene",
        "ready_hygiene_catalog",
        "update_ready_hygiene_stamp",
    ]
    assert not any(node["id"].endswith("_1") or node["id"].endswith("_30") for node in path["nodes"])


def test_survey_inbox_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "survey_inbox")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_inbox_survey",
        "inbox_survey_catalog",
        "update_inbox_survey_stamp",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("classify_inbox_repo_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_survey_ready_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "survey_ready")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_ready_survey",
        "ready_survey_catalog",
        "update_ready_survey_stamp",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("classify_ready_repo_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_reap_over_budget_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "reap_over_budget")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_over_budget_reap",
        "over_budget_catalog",
        "summarize_over_budget_reap",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_budget_receipt_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_plan_pass_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "plan_pass")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_pass_plan",
        "plan_catalog",
        "persist_pass_plan",
        "summarize_pass_plan",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_plan_repo_")
        or node["id"].startswith("build_repo_plan_fragment_")
        or node["id"].startswith("record_repo_plan_fragment_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_select_implement_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "select_implement")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_implementation_selection",
        "implementation_selection_catalog",
        "persist_implementation_selection",
        "summarize_implementation_selection",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_implementation_repo_")
        or node["id"].startswith("inspect_implementation_eligibility_")
        or node["id"].startswith("select_implementation_eligibility_gate_")
        or node["id"].startswith("record_eligible_implementation_repo_")
        or node["id"].startswith("record_ineligible_implementation_repo_")
        or node["id"].startswith("select_implementation_slot_outcome_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_refresh_occupancy_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "refresh_occupancy")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_occupancy_refresh",
        "occupancy_catalog",
        "persist_occupancy_refresh",
        "summarize_occupancy_refresh",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_live_receipt_")
        or node["id"].startswith("inspect_live_receipt_")
        or node["id"].startswith("select_occupancy_repo_")
        or node["id"].startswith("list_occupancy_pull_requests_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_reap_stale_implementing_path_is_a_handful_of_effectors():
    path = next(
        p for p in describe_package()["paths"] if p["id"] == "reap_stale_implementing"
    )
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_stale_implementing_reap",
        "stale_implementing_catalog",
        "persist_stale_implementing_reap",
        "summarize_stale_implementing_reap",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_stale_repo_")
        or node["id"].startswith("list_stale_repo_")
        or node["id"].startswith("select_stale_candidate_")
        or node["id"].startswith("restore_stale_issue_ready_")
        or         node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_stale_worktree_reap_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "stale_worktree_reap")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "collect_stale_worktree_candidates",
        "stale_worktree_catalog",
        "summarize_stale_worktree_reap",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("classify_stale_worktree_")
        or node["id"].startswith("keep_stale_worktree_")
        or node["id"].startswith("remove_stale_worktree_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_4")
        for node in path["nodes"]
    )


def test_leftover_closeout_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "leftover_closeout")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_leftover_closeout",
        "leftover_catalog",
        "update_leftover_stamp",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_leftover_")
        or node["id"].startswith("list_leftover_")
        or node["id"].startswith("classify_leftover_")
        or node["id"].startswith("record_leftover_")
        or node["id"].startswith("park_leftover_")
        or node["id"].startswith("reduce_leftover_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_closeout_prs_path_is_a_handful_of_effectors():
    path = next(p for p in describe_package()["paths"] if p["id"] == "closeout_prs")
    ids = [node["id"] for node in path["nodes"]]
    assert ids == [
        "prepare_pr_closeout",
        "closeout_catalog",
        "persist_pr_closeout",
        "summarize_pr_closeout",
    ]
    assert len(ids) < 8
    assert not any(
        node["id"].startswith("select_pr_closeout_slot_")
        or node["id"].startswith("run_pr_closeout_slot_")
        or node["id"].startswith("record_pr_closeout_slot_")
        or node["id"].endswith("_1")
        or node["id"].endswith("_30")
        for node in path["nodes"]
    )


def test_factory_pass_docs_match_package_atom_order():
    import re

    ids = [
        "self_repair",
        "pr_triage",
        "stale_worktree_reap",
        "issue_triage",
        "select_next_issue",
        "issue_to_pr",
        "pr_triage_after",
        "record_pass",
        "factory_pass_terminal",
    ]
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    assert [node["id"] for node in path["nodes"]] == ids
    mermaid = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )
    top = mermaid.split("```mermaid")[1].split("```")[0]
    def mermaid_id(atom: str) -> str:
        return "".join("FF" if part == "ff" else part.title() for part in atom.split("_"))

    for atom in ids:
        assert mermaid_id(atom) in top, atom
    graph = (Path(__file__).resolve().parents[1] / "docs" / "GRAPH.md").read_text(
        encoding="utf-8"
    )
    section = graph.split("### `factory_pass`")[1].split("### `self_repair`")[0]
    listed = re.findall(r"`([a-z_]+)`", section.split("| Atom |")[0])
    # Spine list in the text block names every live atom in order.
    found = [atom for atom in listed if atom in set(ids)]
    assert found[: len(ids)] == ids or all(atom in section for atom in ids)


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
    assert injected["issue_to_pr"]["live"] is True
    assert injected["pr_triage"]["live"] is True


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
        "summarize_issue_to_pr",
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
        "summarize_self_repair": [
            "self_repair_preflight",
            "self_repair_push_main",
            "self_repair_activate",
            "self_repair_close",
        ],
    }
    assert not any(
        node in {"pr_create", "pr_review", "pr_merge", "pr_repair"}
        for node in conduction
    )


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


def test_factory_path_uses_authored_record_pass_result():
    tick = {"ok": True, "health": "progress", "progress": 1, "remaining": {"ready": 2}}
    out = _host(
        "factory_pass",
        {
            "record_pass": {
                "id": "record_pass",
                "status": "completed",
                "output": {"values": {"ok": True, "tick": tick, "result": tick}},
            }
        },
    )
    assert (
        out["ok"] is True
        and out["health"] == "progress"
        and out["remaining"] == {"ready": 2}
    )


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


def test_no_dangling_when_upstream():
    for path in describe_package()["paths"]:
        ids = {node["id"] for node in path["nodes"]}
        for node in path["nodes"]:
            when = node.get("when") or {}
            upstream = when.get("upstream")
            if not upstream:
                continue
            assert upstream in ids, f"{path['id']}:{node['id']} when.upstream missing"
            assert upstream in (node.get("conduction") or []), (
                f"{path['id']}:{node['id']} when.upstream not in conduction"
            )


def test_parent_814_moving_forward_does_not_replace_factory():
    """#814: moving → repair does not fire; not-moving repair still hosts 2–4."""
    from lokay.proc.classify_auto_repair import classify

    assert classify({}, {"health": "progress"})["route"] == "pass"
    assert classify({}, {"health": "carrier_failed"})["route"] == "repair"
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    by = {n["id"]: n for n in path["nodes"]}
    assert by["pr_triage"].get("when") in (None, {})
    assert by["stale_worktree_reap"].get("when") in (None, {})
    assert by["issue_triage"].get("when") in (None, {})
    assert by["pr_triage"]["conduction"] == ["self_repair"]
    assert "self_repair" in by["issue_triage"]["conduction"]


def test_leftover_fail_routes_host_not_recovery():
    desc = describe_package()
    factory = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    daemon = next(p for p in desc["paths"] if p["id"] == "daemon_cycle")
    leftover = next(p for p in desc["paths"] if p["id"] == "leftover_closeout")
    factory_ids = [n["id"] for n in factory["nodes"]]
    daemon_ids = [n["id"] for n in daemon["nodes"]]
    leftover_ids = [n["id"] for n in leftover["nodes"]]
    assert "recovery_mill" not in factory_ids
    assert "recovery_mill" not in daemon_ids
    assert daemon_ids == ["run_factory_pass", "summarize_daemon_cycle"]
    assert leftover_ids == [
        "prepare_leftover_closeout",
        "leftover_catalog",
        "update_leftover_stamp",
    ]
    assert factory_ids[:4] == [
        "self_repair",
        "pr_triage",
        "stale_worktree_reap",
        "issue_triage",
    ]
    by = {n["id"]: n for n in factory["nodes"]}
    assert by["pr_triage"].get("when") in (None, {})
    assert by["issue_triage"].get("when") in (None, {})
    assert "record_pass" in factory_ids
    assert "recovery_mill" not in leftover_ids


def test_parked_first_row_selects_next_row_same_pass():
    path = next(p for p in describe_package()["paths"] if p["id"] == "factory_pass")
    by = {n["id"]: n for n in path["nodes"]}
    assert by["select_next_issue"]["when"] == {
        "upstream": "issue_triage",
        "path": "route",
        "equals": "no",
    }
    assert "issue_triage" in by["select_next_issue"]["conduction"]
    assert by["pr_triage_after"]["when"] == {
        "upstream": "issue_to_pr",
        "path": "route",
        "equals": "done",
    }
    assert "issue_to_pr" in by["pr_triage_after"]["conduction"]
    ids = [n["id"] for n in path["nodes"]]
    assert ids.index("issue_triage") < ids.index("select_next_issue")
    assert ids.index("select_next_issue") < ids.index("issue_to_pr")
    assert ids.index("issue_to_pr") < ids.index("pr_triage_after")


def test_parent_selected_pass_does_not_conduct_hygiene_timeouts():
    import tomllib

    package = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    factory = next(
        path for path in package["correlation_paths"] if path["id"] == "factory_pass"
    )
    hygiene = {
        "survey_prs",
        "survey_inbox",
        "survey_ready",
        "dispatch_triage",
        "closeout_prs",
        "reap_stale_worktrees",
        "leftover_catalog",
        "recovery_mill",
    }
    ids = {node["id"] for node in factory["effectors"]}
    assert hygiene.isdisjoint(ids)
    for node in factory["effectors"]:
        timeout = (node.get("adapter") or {}).get("timeout_seconds")
        if node["id"] in {
            "self_repair",
            "pr_triage",
            "issue_triage",
            "issue_to_pr",
            "pr_triage_after",
        }:
            continue
        assert timeout not in {1800, 7200} or node["id"] == "stale_worktree_reap"
