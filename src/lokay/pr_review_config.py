"""Canonical, credential-free identity for the configured PR-review engine."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from lokay.config import Config

_HASH = re.compile(r"^[a-f0-9]{64}$")
_MANIFEST_SCHEMA = "lokay.pr-review-config/1"


class ReviewConfigError(ValueError):
    """The configured review engine is not the trusted production engine."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ReviewConfigError("trusted_file_unavailable") from exc


def _trusted_path(path: Path | None, *, executable: bool = False) -> Path:
    if path is None:
        raise ReviewConfigError("trusted_file_missing")
    candidate = Path(path).expanduser()
    try:
        if candidate.is_symlink():
            raise ReviewConfigError("trusted_file_symlink")
        resolved = candidate.resolve(strict=True)
        if resolved != candidate.absolute():
            raise ReviewConfigError("trusted_file_symlink")
        if not resolved.is_file() or not os.access(resolved, os.X_OK if executable else os.R_OK):
            raise ReviewConfigError("trusted_file_missing")
    except OSError as exc:
        raise ReviewConfigError("trusted_file_unavailable") from exc
    return resolved


def _credential_keys(value: Any) -> bool:
    if isinstance(value, Mapping):
        forbidden = {
            "api_key", "api_key_cmd", "auth_token", "auth_token_cmd",
            "password", "token", "secret",
        }
        if any(str(key).lower() in forbidden for key in value):
            return True
        return any(_credential_keys(item) for item in value.values())
    if isinstance(value, list):
        return any(_credential_keys(item) for item in value)
    return False


def _json_file(path: Path) -> Any:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewConfigError("trusted_file_invalid") from exc
    return value


def _file_digests(cfg: Config) -> dict[str, str]:
    return {
        "opencodereview_sha256": _sha256_bytes(_trusted_path(cfg.pr_review_ocr_config)),
        "rule_sha256": _sha256_bytes(_trusted_path(cfg.pr_review_rule_file)),
        "tools_sha256": _sha256_bytes(_trusted_path(cfg.pr_review_tools_file)),
        "sandbox_template_sha256": _sha256_bytes(_trusted_path(cfg.pr_review_sandbox_profile)),
    }


def canonical_review_payload(cfg: Config) -> dict[str, Any]:
    """Return the secret-free identity covered by ``config_sha256``."""
    binary = _trusted_path(cfg.pr_review_binary, executable=True)
    plugin = _trusted_path(Path(cfg.pr_review_plugin_command), executable=True)
    provider_config = _trusted_path(cfg.pr_review_ocr_config)
    provider_value = _json_file(provider_config)
    if not isinstance(provider_value, dict) or _credential_keys(provider_value):
        raise ReviewConfigError("credential_materialized")
    if provider_value.get("provider") != cfg.pr_review_provider:
        raise ReviewConfigError("provider_config_mismatch")
    providers = provider_value.get("providers")
    selected = providers.get(cfg.pr_review_provider) if isinstance(providers, Mapping) else None
    if not isinstance(selected, Mapping):
        raise ReviewConfigError("provider_config_mismatch")
    if selected.get("url") != cfg.pr_review_provider_endpoint_url or selected.get("model") != cfg.pr_review_model:
        raise ReviewConfigError("provider_config_mismatch")
    if set(provider_value) != {"provider", "providers", "llm"} or provider_value.get("llm") != {}:
        raise ReviewConfigError("provider_config_policy_mismatch")
    if set(providers) != {cfg.pr_review_provider} or set(selected) != {"url", "model"}:
        raise ReviewConfigError("provider_config_policy_mismatch")
    return {
        "schema": _MANIFEST_SCHEMA,
        "engine": {
            "name": "open-code-review",
            "version": str(cfg.pr_review_binary_version),
            "binary_path": str(binary),
            "binary_sha256": str(cfg.pr_review_binary_sha256).lower(),
        },
        "plugin": {
            "command": str(plugin),
            "args": [str(item) for item in cfg.pr_review_plugin_args],
            "timeout_seconds": int(cfg.pr_review_plugin_timeout_seconds),
        },
        "provider": {
            "name": str(cfg.pr_review_provider),
            "endpoint_url": str(cfg.pr_review_provider_endpoint_url),
            "model": str(cfg.pr_review_model),
            "environment_names": sorted(str(item) for item in cfg.pr_review_provider_env),
            "config_sha256": _sha256_bytes(provider_config),
        },
        "review": {
            "effort": str(cfg.pr_review_effort),
            "timeout_minutes": int(cfg.pr_review_timeout_minutes),
            "max_tokens_budget": int(cfg.pr_review_max_tokens_budget),
            "concurrency": 1,
        },
        "trusted_files": _file_digests(cfg),
        "sandbox": {
            "executable": str(_trusted_path(Path(cfg.pr_review_sandbox_command[0]) if cfg.pr_review_sandbox_command else None, executable=True)),
            "command": [str(item) for item in cfg.pr_review_sandbox_command],
            "profile_path": str(_trusted_path(cfg.pr_review_sandbox_profile)),
        },
    }


def review_config_sha256(cfg: Config) -> str:
    return hashlib.sha256(_canonical(canonical_review_payload(cfg))).hexdigest()


def expected_review_manifest(cfg: Config) -> dict[str, Any]:
    """Build the operator manifest from the same canonical payload."""
    payload = canonical_review_payload(cfg)
    manifest = dict(payload)
    manifest["config_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return manifest


def _manifest_path(cfg: Config) -> Path | None:
    value = getattr(cfg, "pr_review_manifest", None)
    if not value:
        return None
    return Path(value).expanduser()


def verify_review_config(cfg: Config) -> None:
    """Fail closed unless config, trusted files, and operator manifest agree."""
    payload = canonical_review_payload(cfg)
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    if str(cfg.pr_review_config_sha256).lower() != digest:
        raise ReviewConfigError("config_digest_mismatch")
    manifest_path = _manifest_path(cfg)
    if manifest_path is None:
        raise ReviewConfigError("config_manifest_missing")
    try:
        manifest_path = _trusted_path(manifest_path)
        manifest = json.loads(manifest_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewConfigError("config_manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise ReviewConfigError("config_manifest_invalid")
    if manifest != {**payload, "config_sha256": digest}:
        raise ReviewConfigError("config_manifest_mismatch")
    if manifest.get("config_sha256") != digest:
        raise ReviewConfigError("config_manifest_mismatch")
