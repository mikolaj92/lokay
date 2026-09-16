from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lokay.config import Config, RepoConfig
from lokay.pr_review_config import (
    ReviewConfigError,
    canonical_review_payload,
    expected_review_manifest,
    review_config_sha256,
    verify_review_config,
)


def _armed_config(tmp_path: Path) -> Config:
    binary = tmp_path / "ocr"
    binary.write_bytes(b"pinned binary")
    binary.chmod(0o700)
    plugin = tmp_path / "review-plugin"
    plugin.write_bytes(b"pinned plugin")
    plugin.chmod(0o700)
    provider = tmp_path / "opencodereview.json"
    provider.write_text(
        json.dumps(
            {
                "provider": "openai",
                "providers": {
                    "openai": {
                        "url": "https://gateway.example/v1",
                        "model": "review-model",
                    }
                },
                "llm": {},
            }
        ),
        encoding="utf-8",
    )
    rule = tmp_path / "rule.json"
    rule.write_text("{\"rule\": true}", encoding="utf-8")
    tools = tmp_path / "tools.json"
    tools.write_text("{\"task_done\": {}}", encoding="utf-8")
    sandbox = tmp_path / "review.sb"
    sandbox.write_text("(version 1)\n", encoding="utf-8")
    manifest = tmp_path / "config-manifest.json"
    cfg = Config(
        mode="live",
        repos=[RepoConfig("acme/demo", tmp_path)],
        merge_enabled=True,
        require_llm_review=True,
        pr_review_plugin_command=str(plugin),
        pr_review_plugin_args=["--json"],
        pr_review_provider="openai",
        pr_review_provider_endpoint_url="https://gateway.example/v1",
        pr_review_model="review-model",
        pr_review_ocr_config=provider,
        pr_review_manifest=manifest,
        pr_review_provider_env=["OCR_LLM_API_KEY"],
        pr_review_binary=binary,
        pr_review_binary_version="v1.12.0",
        pr_review_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        pr_review_rule_file=rule,
        pr_review_tools_file=tools,
        pr_review_sandbox_profile=sandbox,
        pr_review_sandbox_command=["/usr/bin/sandbox-exec", "-f", str(sandbox), "--"],
        pr_review_timeout_minutes=15,
        pr_review_max_tokens_budget=100000,
        pr_review_effort="medium",
    )
    cfg.pr_review_config_sha256 = review_config_sha256(cfg)
    manifest.write_text(
        json.dumps(expected_review_manifest(cfg), sort_keys=True), encoding="utf-8"
    )
    return cfg


def test_canonical_review_digest_excludes_credential_value(tmp_path: Path, monkeypatch):
    cfg = _armed_config(tmp_path)
    monkeypatch.setenv("OCR_LLM_API_KEY", "first-secret")
    first = review_config_sha256(cfg)
    monkeypatch.setenv("OCR_LLM_API_KEY", "second-secret")
    second = review_config_sha256(cfg)

    assert first == second
    encoded = json.dumps(canonical_review_payload(cfg), sort_keys=True)
    assert "first-secret" not in encoded
    assert "second-secret" not in encoded
    assert canonical_review_payload(cfg)["provider"]["environment_names"] == [
        "OCR_LLM_API_KEY"
    ]


def test_programmatic_review_manifest_and_trusted_hash_verification(tmp_path: Path):
    cfg = _armed_config(tmp_path)

    verify_review_config(cfg)

    cfg.pr_review_config_sha256 = "0" * 64
    with pytest.raises(ReviewConfigError, match="config_digest_mismatch"):
        verify_review_config(cfg)


def test_programmatic_review_verification_rejects_tampered_provider_config(
    tmp_path: Path,
):
    cfg = _armed_config(tmp_path)
    cfg.pr_review_ocr_config.write_text(
        '{"provider":"openai","providers":{"openai":{"url":"https://evil.example/v1","model":"review-model"}},"llm":{}}',
        encoding="utf-8",
    )

    with pytest.raises(ReviewConfigError, match="provider_config_mismatch"):
        verify_review_config(cfg)


def test_programmatic_review_verification_rejects_symlinked_trusted_file(tmp_path: Path):
    cfg = _armed_config(tmp_path)
    target = tmp_path / "real-rule.json"
    target.write_text(cfg.pr_review_rule_file.read_text(), encoding="utf-8")
    cfg.pr_review_rule_file.unlink()
    cfg.pr_review_rule_file.symlink_to(target)

    with pytest.raises(ReviewConfigError, match="trusted_file_symlink"):
        verify_review_config(cfg)


def test_programmatic_review_verification_rejects_credential_in_provider_config(
    tmp_path: Path,
):
    cfg = _armed_config(tmp_path)
    cfg.pr_review_ocr_config.write_text(
        '{"provider":"openai","providers":{"openai":{"url":"https://gateway.example/v1","model":"review-model","api_key":"materialized"}},"llm":{}}',
        encoding="utf-8",
    )

    with pytest.raises(ReviewConfigError, match="credential_materialized"):
        verify_review_config(cfg)
