"""Selection preflight is an authored graph gate, not a Python review pipeline."""
import tomllib
from pathlib import Path
from types import SimpleNamespace

from lokay.organ.review_boundary import handle_review_boundary

ROOT = Path(__file__).resolve().parents[1]


def test_graph_checks_vendor_scope_before_review():
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    path = next(p for p in package["correlation_paths"] if p["id"] == "pr_triage")
    nodes = {node["id"]: node for node in path["effectors"]}
    scope = nodes["select_pr_review_scope"]
    assert scope["when"] == {"upstream": "resolve_sha_review", "path": "route", "equals": "agent"}
    assert "collect_pr_review_evidence" in scope["conduction"]
    assert "select_pr_review_scope" in nodes["pr_review_agent"]["conduction"]
    assert nodes["pr_review_agent"]["when"] == {"upstream": "select_pr_review_scope", "path": "route", "equals": "ready"}
    assert "select_pr_review_scope" in nodes["validate_pr_review"]["conduction"]


def test_scope_failure_reaches_review_terminal_without_llm():
    result = handle_review_boundary(
        "validate_pr_review", {},
        {"resolve_sha_review": {"route": "agent"},
         "select_pr_review_scope": {"ok": True, "route": "fail_closed", "reason": "ocr_scope_incomplete"}},
        {"repo": "o/r", "pr_number": 7, "branch": "b", "live": True},
    )
    assert result["route"] == "fail_closed"
    assert result["reason"] == "ocr_scope_incomplete"


def test_native_scope_gate_blocks_llm_and_cached_review_skips_scope(tmp_path):
    from support.native_path import run_overridden_path
    for resolved, scope, expected_scope, expected_agent in (
        ("agent", "ready", "succeeded", "succeeded"),
        ("agent", "fail_closed", "succeeded", "skipped"),
        ("cached", "ready", "skipped", "skipped"),
    ):
        result = run_overridden_path(tmp_path, "pr_triage", {
            "classify_pr_triage_checks": {"route": "review"},
            "resolve_sha_review": {"route": resolved},
            "select_pr_review_scope": {"route": scope},
            "validate_pr_review": {"route": "fail_closed"},
        }, run_id=f"{resolved}-{scope}")
        nodes = result["effector_results"]
        assert nodes["select_pr_review_scope"]["status"] == expected_scope
        assert nodes["pr_review_agent"]["status"] == expected_agent
        assert nodes["validate_pr_review"]["status"] == "succeeded"
        assert nodes["pr_merge"]["status"] == "skipped"


def test_scope_atom_uses_plugin_operation_not_review(monkeypatch):
    from lokay.proc import select_pr_review_scope as atom
    from lokay.proc import run_pr_review_agent
    from lokay import config
    cfg = SimpleNamespace(pr_review_plugin_args=["--max-input-bytes", "4194304"])
    request = {key: key for key in ("repo", "pr", "head_sha", "base_ref_sha", "comparison_base_sha",
                                  "diff_sha256", "task_identity_sha256", "review_config_sha256")}
    monkeypatch.setattr(config, "load_config", lambda _: cfg)
    monkeypatch.setattr(run_pr_review_agent, "plugin_request", lambda *args: request)
    calls = []
    def invoke(configured, given):
        calls.append(configured.pr_review_plugin_args)
        return {"ok": True, "schema": "lokay.review-scope/1", **request, "preview": {"files": []}}
    monkeypatch.setattr(atom, "invoke_plugin", invoke)
    assert atom.select(config_path=None, repo="o/r", pr=7, evidence={}, live=True)["route"] == "ready"
    assert calls == [["--max-input-bytes", "4194304", "--operation", "scope"]]
    assert cfg.pr_review_plugin_args == ["--max-input-bytes", "4194304"]
