from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PLUGIN_SRC = Path(__file__).parents[1] / "plugins/pr_review_open_code_review/src"
sys.path.insert(0, str(PLUGIN_SRC))

from lokay_review_open_code_review.contract import normalize_result, sha256_json  # noqa: E402
from lokay.proc.validate_pr_review import validate_result  # noqa: E402
from lokay.proc.publish_pr_review import publish  # noqa: E402

FIXTURES = Path(__file__).parents[1] / "plugins/pr_review_open_code_review/tests/fixtures/upstream_v1_12"


def _request():
    task = {"repo": "acme/demo", "type": "Issue", "state": "OPEN", "number": 42,
            "title": "Prevent invalid save", "body": "Acceptance: reject blank IDs.",
            "url": "https://github.com/acme/demo/issues/42"}
    return {"schema": "lokay.review-request/1", "repo": "acme/demo", "pr": 84,
            "head_ref": "ai/fix/42-demo", "head_sha": "b" * 40,
            "head_repo": "acme/demo", "base_ref": "main", "base_ref_sha": "a" * 40,
            "comparison_base_sha": "c" * 40, "repo_path": "/tmp/review-checkout",
            "changed_ranges": {"src/demo.py": [(12, 13)]}, "review_config_sha256": "9" * 64,
            "diff_paths": [{"path": "src/demo.py", "old_path": "", "status": "modified"}],
            "diff_sha256": "d" * 64, "task": task, "task_identity_sha256": sha256_json(task),
            "engine": {"binary_sha256": "f" * 64, "config_sha256": "9" * 64,
                       "provider": "example-provider", "model": "example-model"}}


def _result():
    request = _request()
    upstream = json.loads((FIXTURES / "review-complete.json").read_text())
    upstream["manifest"]["repository"]["identity_sha256"] = __import__("hashlib").sha256(b"github.com/acme/demo").hexdigest()
    result = normalize_result(
        request, upstream,
        engine={"name": "open-code-review", "version": "v1.12.7", "binary_sha256": "f" * 64,
                "provider": "example-provider", "model": "example-model", "config_sha256": "9" * 64},
        changed_ranges=request["changed_ranges"],
    )
    return request, result


def test_vendor_comments_close_review_as_request_changes_when_budget_is_partial():
    request = _request()
    upstream = json.loads((FIXTURES / "review-complete.json").read_text())
    upstream["manifest"]["repository"]["identity_sha256"] = __import__("hashlib").sha256(
        b"github.com/acme/demo"
    ).hexdigest()
    upstream["summary"]["budget_exceeded"] = True
    upstream["status"] = "partial"
    upstream["manifest"]["terminal_state"] = "partial"
    result = normalize_result(
        request, upstream,
        engine={"name": "open-code-review", "version": "v1.12.7", "binary_sha256": "f" * 64,
                "provider": "example-provider", "model": "example-model", "config_sha256": "9" * 64},
        changed_ranges=request["changed_ranges"],
    )
    result["coverage"]["reviewable_paths"] = [
        {"path": "src/demo.py", "old_path": "", "status": "modified"}
    ]
    selected = validate_result(result, request)
    assert selected["route"] == "valid"
    assert selected["decision"]["verdict"] == "request_changes"
    assert selected["decision"]["findings"]


def test_host_validation_runs_without_plugin_import_path():
    import subprocess
    request, result = _result()
    request["engine"]["version"] = "v1.12.7"
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "lokay.proc.validate_pr_review",
         "--result-json", json.dumps(result), "--request-json", json.dumps(request)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["decision"]["verdict"] == "request_changes"


def test_policy_maps_every_finding_even_low_severity_to_request_changes():
    request, result = _result()
    result["findings"][0]["severity"] = "low"
    result["coverage"]["reviewable_paths"] = [{"path": "src/demo.py", "old_path": "", "status": "modified"}]
    selected = validate_result(result, request)
    assert selected["route"] == "valid"
    assert selected["decision"]["verdict"] == "request_changes"
    assert selected["decision"]["findings"][0]["severity"] == "low"
    assert selected["decision"]["reviewed_head_sha"] == request["head_sha"]
    assert selected["decision"]["task"] == request["task"]


def test_publish_fails_closed_if_durable_artifact_cannot_be_written(monkeypatch):
    from pathlib import Path

    request, result = _result()
    selected = validate_result(result, request)
    selected["route"] = "publish"
    selected["selected_route"] = "publish"
    selected["ok"] = True
    cfg = SimpleNamespace(max_request_changes_per_pr=2)
    monkeypatch.setattr("lokay.proc.publish_pr_review.mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        "lokay.proc.publish_pr_review.persist_result",
        lambda **_kwargs: {"ok":False, "reason":"artifact_write_failed"},
    )
    out = publish(
        cfg=cfg, repo=request["repo"], pr=request["pr"], evidence=request,
        selected=selected, live=False,
    )
    assert out["ok"] is False
    assert out.get("route") == "fail_closed"


def test_publish_persists_all_upstream_review_fingerprints(tmp_path):
    from lokay.proc import publish_pr_review

    request, result = _result()
    selected = validate_result(result, request)
    selected.update(route="publish", request_changes_count=0)
    cfg = SimpleNamespace(
        max_request_changes_per_pr=2,
        pr_review_artifacts_dir=tmp_path,
        pr_review_config_sha256="9" * 64,
        pr_review_binary_version="v1.12.0",
        pr_review_binary_sha256="f" * 64,
        pr_review_provider="example-provider",
        pr_review_model="example-model",
    )

    out = publish_pr_review.publish(
        cfg=cfg, repo=request["repo"], pr=request["pr"],
        evidence=request, selected=selected, live=False,
    )

    assert out["ok"] is True
    artifacts = list(tmp_path.glob("results/*/*/*.json"))
    assert len(artifacts) == 1
    stored = json.loads(artifacts[0].read_text())
    decision = stored["decision"]
    evidence = result["evidence"]
    assert decision["review_input_fingerprint_sha256"] == evidence["input_fingerprint_sha256"]
    assert decision["review_preview_sha256"] == evidence["preview_sha256"]
    assert decision["review_rule_config_sha256"] == evidence["upstream_execution"]["rule_config_sha256"]
    assert decision["review_runtime_config_sha256"] == evidence["upstream_execution"]["runtime_config_sha256"]


def test_policy_only_approves_complete_zero_finding_result():
    request, result = _result()
    result["findings"] = []
    result["coverage"]["reviewable_paths"] = [{"path": "src/demo.py", "old_path": "", "status": "modified"}]
    selected = validate_result(result, request)
    assert selected["route"] == "valid"
    assert selected["decision"]["verdict"] == "approve"


def test_policy_rejects_omitted_changed_paths_and_requires_deleted_only_exclusions():
    request, result = _result()
    result["coverage"]["reviewable_paths"] = []
    assert validate_result(result, request)["route"] == "fail_closed"

    request, result = _result()
    request["diff_paths"].append({"path": "old.py", "old_path": "", "status": "deleted"})
    result["coverage"]["excluded"] = [{"path": "old.py", "old_path": "", "status": "deleted"}]
    result["diff_paths"].append({"path": "old.py", "old_path": "", "status": "deleted"})
    assert validate_result(result, request)["route"] == "valid"
    result["coverage"]["excluded"] = []
    assert validate_result(result, request)["route"] == "fail_closed"


def test_full_findings_and_canonical_task_survive_parent_repair_selection():
    from lokay.proc.select_pr_repair_department import select

    request, result = _result()
    selected = validate_result(result, request)
    repair = select(
        {"repo": "acme/demo", "pr": 84, "branch": "ai/fix/42-demo",
         "repair_start_head_sha": request["head_sha"],
         "triage": {"repairable": True, "repair_kind": "review", "review": selected["decision"]}},
        enabled=True, triage_ran=True, budget=2, home=Path("/tmp/lokay-review-test-home"),
    )
    assert repair["route"] == "repair"
    assert repair["review"]["findings"][0]["path"] == "src/demo.py"
    assert repair["review"]["task"] == request["task"]
    assert repair["review"]["reviewed_head_sha"] == request["head_sha"]
    assert repair["repair_kind"] == "review"
    assert repair["review_result_sha256"] == selected["decision"]["review_result_sha256"]


def test_parent_repair_selection_fails_closed_on_canonical_task_digest_drift():
    from lokay.proc.select_pr_repair_department import select

    request, result = _result()
    selected = validate_result(result, request)
    decision = dict(selected["decision"])
    decision["task"] = {**decision["task"], "body": "changed after canonical review"}
    repair = select(
        {"repo": "acme/demo", "pr": 84, "branch": "ai/fix/42-demo",
         "triage": {"repairable": True, "repair_kind": "review", "review": decision}},
        enabled=True, triage_ran=True, budget=2,
    )
    assert repair["route"] == "fail_closed"
    assert repair["reason"] == "review_repair_handoff_incomplete"


def test_review_repair_freshness_rechecks_the_canonical_open_issue(monkeypatch):
    from lokay.proc.run_parent_pr_repair_subflow import _review_task_is_current

    task = {
        "repo": "acme/demo", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "original acceptance", "url": "https://github.com/acme/demo/issues/42",
    }
    task_digest = sha256_json(task)
    selected = {
        "repair_kind": "review", "repo": "acme/demo", "pr": 84,
        "branch": "ai/fix/42-demo", "task": task, "task_identity_sha256": task_digest,
        "review": {"task": task, "task_identity_sha256": task_digest},
    }
    monkeypatch.setattr(
        "lokay.config.load_config",
        lambda _path: SimpleNamespace(branch_prefix="ai/fix"),
    )
    monkeypatch.setattr(
        "lokay.proc._common.runner",
        lambda _cfg: object(),
    )
    canonical = {**task, "identity_sha256": task_digest}
    monkeypatch.setattr(
        "lokay.pr_review_io.resolve_canonical_task",
        lambda *_args, **_kwargs: canonical,
    )

    assert _review_task_is_current(selected, config_path="config.yaml", live=True)

    canonical["body"] = "changed canonical acceptance"
    assert not _review_task_is_current(selected, config_path="config.yaml", live=True)


def test_review_agent_revalidates_pr_after_plugin_before_returning_result(monkeypatch):
    from lokay.proc import run_pr_review_agent

    from types import SimpleNamespace
    cfg = SimpleNamespace(branch_prefix="ai/fix")
    evidence = {
        "repo": "acme/demo", "pr": 84, "head_ref": "ai/fix/42-demo",
        "head_repo": "acme/demo", "head_sha": "b" * 40,
        "base_ref": "main", "base_ref_sha": "a" * 40,
        "comparison_base_sha": "c" * 40, "diff_sha256": "d" * 64,
        "task_identity_sha256": "e" * 64,
    }
    identity = {key: evidence[key] for key in (
        "repo", "pr", "head_ref", "head_repo", "head_sha", "base_ref",
        "base_ref_sha", "comparison_base_sha", "diff_sha256", "task_identity_sha256",
    )}
    task = {"repo":"acme/demo", "type":"Issue", "state":"OPEN", "number":42,
            "title":"task", "body":"full task body", "url":"https://github.com/acme/demo/issues/42"}
    evidence["task"] = task
    snapshots = iter([identity, {**identity, "head_sha": "f" * 40}])
    calls = []
    monkeypatch.setattr(run_pr_review_agent, "load_config", lambda _path: cfg)
    monkeypatch.setattr(run_pr_review_agent, "plugin_request", lambda *_args: {"request": True})
    monkeypatch.setattr(run_pr_review_agent, "invoke_plugin", lambda *_args: {
        "ok": True, "repo": "acme/demo", "pr": 84,
        "head_ref": "ai/fix/42-demo", "head_repo": "acme/demo", "base_ref": "main",
        "head_sha": "b" * 40, "base_ref_sha": "a" * 40,
        "comparison_base_sha": "c" * 40, "diff_sha256": "d" * 64,
        "task_identity_sha256": "e" * 64,
    })
    monkeypatch.setattr(
        "lokay.pr_review_io.revalidate_pr_identity",
        lambda *_args, **_kwargs: calls.append(True) or next(snapshots),
    )

    result = run_pr_review_agent.run_review_agent(
        config_path=None, repo="acme/demo", pr=84, evidence=evidence, live=True,
    )

    assert result["ok"] is False
    assert result.get("route") == "fail_closed"
    assert len(calls) == 2


def test_review_task_is_not_truncated_in_plugin_request(monkeypatch):
    from lokay.proc.run_pr_review_agent import plugin_request
    from types import SimpleNamespace

    body = "acceptance requirement " * 1000
    task = {"repo":"acme/demo", "type":"Issue", "state":"OPEN", "number":42,
            "title":"task", "body":body, "url":"https://github.com/acme/demo/issues/42"}
    cfg = SimpleNamespace(
        pr_review_config_sha256="9"*64, pr_review_binary_version="v1.12.0",
        pr_review_binary=None, pr_review_binary_sha256="f"*64,
        pr_review_provider="p", pr_review_provider_endpoint_url="https://p.example",
        pr_review_model="m", pr_review_effort="medium", pr_review_timeout_minutes=15,
        pr_review_max_tokens_budget=100, pr_review_rule_file=None,
        pr_review_tools_file=None, pr_review_ocr_config=None,
        pr_review_sandbox_command=[], pr_review_sandbox_profile=None,
        pr_review_provider_env=[],
    )
    evidence = {"task":task}

    assert plugin_request(cfg, "acme/demo", 84, evidence)["task"]["body"] == body


def test_policy_fails_closed_on_identity_or_coverage_drift():
    request, result = _result()
    result["head_sha"] = "e" * 40
    assert validate_result(result, request)["route"] == "fail_closed"
    request, result = _result()
    result["coverage"]["failed"] = [{"path": "src/demo.py"}]
    assert validate_result(result, request)["route"] == "fail_closed"


def test_review_agent_archives_redacted_vendor_warnings_on_contract_reject(monkeypatch, tmp_path):
    from lokay.proc import run_pr_review_agent
    from lokay.proc.pr_review_plugin import PluginFailure

    cfg = SimpleNamespace(
        branch_prefix="ai/fix",
        pr_review_artifacts_dir=tmp_path,
        pr_review_config_sha256="9" * 64,
        pr_review_binary_version="v1.12.0",
        pr_review_binary_sha256="f" * 64,
        pr_review_provider="p",
        pr_review_model="m",
    )
    task = {
        "repo": "acme/demo", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "full task body",
        "url": "https://github.com/acme/demo/issues/42",
    }
    evidence = {
        "repo": "acme/demo", "pr": 84, "head_ref": "ai/fix/42-demo",
        "head_repo": "acme/demo", "head_sha": "b" * 40,
        "base_ref": "main", "base_ref_sha": "a" * 40,
        "comparison_base_sha": "c" * 40, "diff_sha256": "d" * 64,
        "task_identity_sha256": "e" * 64, "task": task,
        "diff_paths": [{"path": "src/a.py", "old_path": "", "status": "modified"}],
        "changed_ranges": {"src/a.py": [[1, 1]]},
    }
    identity = {key: evidence[key] for key in (
        "repo", "pr", "head_ref", "head_repo", "head_sha", "base_ref",
        "base_ref_sha", "comparison_base_sha", "diff_sha256", "task_identity_sha256",
    )}
    failure = PluginFailure("ocr_contract_rejected: review has warnings")
    failure.warnings = [{"type": "token_budget_reached", "file": "src/demo.py"}]
    monkeypatch.setattr(run_pr_review_agent, "load_config", lambda _path: cfg)
    monkeypatch.setattr(run_pr_review_agent, "plugin_request", lambda *_args: {"request": True})
    monkeypatch.setattr(run_pr_review_agent, "invoke_plugin", lambda *_args: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(
        "lokay.pr_review_io.revalidate_pr_identity",
        lambda *_args, **_kwargs: identity,
    )

    result = run_pr_review_agent.run_review_agent(
        config_path=None, repo="acme/demo", pr=84, evidence=evidence, live=True,
    )

    assert result["ok"] is False
    assert result.get("route") == "fail_closed"
    artifacts = list(tmp_path.glob("rejections/*/*/*.json"))
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text())
    assert payload["schema"] == "lokay.review-rejection/1"
    assert payload["warnings"] == [{"type": "token_budget_reached", "file": "src/demo.py"}]
