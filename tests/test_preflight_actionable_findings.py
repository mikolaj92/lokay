"""Preflight must name why production cannot start, without exposing config secrets."""
from types import SimpleNamespace

from lokay import preflight_checks as checks


def test_config_finding_names_rejected_fields():
    out = checks.check_config(cfg=SimpleNamespace(validate=lambda: ["pr_review.binary_version must be pinned to v1.12.7"]))
    assert out["ok"] is False
    assert out["code"] == "invalid"
    assert "binary_version" in out["detail"]


def test_review_finding_names_digest_mismatch(monkeypatch):
    from lokay.pr_review_config import ReviewConfigError

    def reject(_):
        raise ReviewConfigError("config_digest_mismatch")

    monkeypatch.setattr("lokay.pr_review_config.verify_review_config", reject)
    out = checks.check_pr_review_config(cfg=SimpleNamespace(live=True, merge_enabled=True, require_llm_review=True))
    assert out["ok"] is False
    assert out["code"] == "untrusted_review_config"
    assert out["detail"] == "config_digest_mismatch"


def test_preflight_rejects_invalid_tool_registry(monkeypatch, tmp_path):
    tools = tmp_path / "tools.json"
    tools.write_text("[]")
    monkeypatch.setattr("lokay.pr_review_config.verify_review_config", lambda _: None)
    out = checks.check_pr_review_config(cfg=SimpleNamespace(
        live=True, merge_enabled=True, require_llm_review=True, pr_review_tools_file=tools))
    assert out["ok"] is False
    assert out["detail"] == "tools_allowlist_invalid"
