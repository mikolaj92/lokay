"""Redacted, immutable review-result artifacts for crash-safe publication recovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from lokay.config import Config

_SHA = re.compile(r"^[a-f0-9]{40}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SECRET_TEXT = re.compile(
    r"(?i)(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._~+/-]{16,}|"
    r"(?:api[_-]?key|token|password|secret)[=: ]+[A-Za-z0-9._~+/-]{12,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("invalid repository identity")
    return value.replace("/", "__")


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        forbidden = {"thinking", "raw_logs", "logs", "stderr", "stdout", "api_key", "api_key_cmd", "auth_token", "auth_token_cmd", "password", "token"}
        return {str(key): _sanitize(item) for key, item in value.items() if str(key).lower() not in forbidden}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _SECRET_TEXT.sub("[redacted]", value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    raise ValueError("unsupported artifact value")


def _artifact(cfg: Config, repo: str, pr: int, evidence: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    refs = {key: str(evidence.get(key) or "").lower() for key in ("head_sha", "base_ref_sha", "comparison_base_sha")}
    hashes = {key: str(value or "").lower() for key, value in {
        "diff_sha256": evidence.get("diff_sha256"),
        "task_identity_sha256": evidence.get("task_identity_sha256"),
        "review_result_sha256": decision.get("review_result_sha256"),
    }.items()}
    if any(not _SHA.fullmatch(value) for value in refs.values()) or any(not _HASH.fullmatch(value) for value in hashes.values()):
        raise ValueError("malformed artifact identity")
    if decision.get("reviewed_head_sha") != refs["head_sha"] or decision.get("task_identity_sha256") != hashes["task_identity_sha256"]:
        raise ValueError("artifact decision identity drift")
    task = evidence.get("task") or {}
    findings = _sanitize(decision.get("findings") or [])
    if not isinstance(task, Mapping) or not isinstance(findings, list):
        raise ValueError("artifact task or findings malformed")
    verdict = str(decision.get("verdict") or "fail_closed")
    if (findings and verdict != "request_changes") or (not findings and verdict != "approve"):
        raise ValueError("artifact verdict and findings disagree")
    if not _HASH.fullmatch(str(cfg.pr_review_config_sha256 or "")):
        raise ValueError("review configuration digest is missing")
    if not _HASH.fullmatch(str(cfg.pr_review_binary_sha256 or "")):
        raise ValueError("review binary digest is missing")
    if not _HASH.fullmatch(str(decision.get("task_identity_sha256") or "")):
        raise ValueError("canonical task digest is missing")
    if hashlib.sha256(_canonical(task)).hexdigest() != hashes["task_identity_sha256"]:
        raise ValueError("canonical task digest mismatch")
    sanitized_task = _sanitize(task)
    return {
        "schema": "lokay.review-artifact/1", "repo": repo, "pr": int(pr),
        "head_ref": str(evidence.get("head_ref") or ""),
        "head_repo": str(evidence.get("head_repo") or ""),
        "base_ref": str(evidence.get("base_ref") or ""),
        "diff_paths": _sanitize(evidence.get("diff_paths") or []),
        "changed_ranges": _sanitize(evidence.get("changed_ranges") or {}),
        "preview_sha256": str((evidence.get("review_execution") or {}).get("preview_sha256") or decision.get("review_preview_sha256") or ""),
        "input_fingerprint_sha256": str((evidence.get("review_execution") or {}).get("input_fingerprint_sha256") or decision.get("review_input_fingerprint_sha256") or ""),
        "upstream_rule_config_sha256": str((evidence.get("review_execution") or {}).get("rule_config_sha256") or decision.get("review_rule_config_sha256") or ""),
        "upstream_runtime_config_sha256": str((evidence.get("review_execution") or {}).get("runtime_config_sha256") or decision.get("review_runtime_config_sha256") or ""),
        **refs, **hashes,
        "review_config_sha256": str(cfg.pr_review_config_sha256),
        "engine": {"version": str(cfg.pr_review_binary_version),
                   "binary_sha256": str(cfg.pr_review_binary_sha256),
                   "provider": str(cfg.pr_review_provider), "model": str(cfg.pr_review_model)},
        "decision": {
            "verdict": verdict,
            "summary": str(_sanitize(str(decision.get("summary") or ""))),
            "findings": findings,
            "reviewed_head_sha": refs["head_sha"],
            "task_identity_sha256": hashes["task_identity_sha256"],
            "review_result_sha256": hashes["review_result_sha256"],
            "review_input_fingerprint_sha256": str(decision.get("review_input_fingerprint_sha256") or ""),
            "review_preview_sha256": str(decision.get("review_preview_sha256") or ""),
            "review_rule_config_sha256": str(decision.get("review_rule_config_sha256") or ""),
            "review_runtime_config_sha256": str(decision.get("review_runtime_config_sha256") or ""),
        },
    }


def persist_result(*, cfg: Config, repo: str, pr: int, evidence: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = _artifact(cfg, repo, pr, evidence, decision)
        directory = Path(cfg.pr_review_artifacts_dir).expanduser().resolve() / "results" / _safe_component(repo) / str(int(pr))
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        body = _canonical(payload) + b"\n"
        digest = hashlib.sha256(body).hexdigest()
        path = directory / f"{payload['head_sha']}-{digest}.json"
        if path.exists() and path.read_bytes() != body:
            return {"ok": False, "reason": "artifact_conflict"}
        if not path.exists():
            temp = directory / f".{path.name}.{os.getpid()}.tmp"
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, path)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
        if path.read_bytes() != body:
            return {"ok": False, "reason": "artifact_verification_failed"}
        return {"ok": True, "path": str(path), "artifact_sha256": digest}
    except (OSError, ValueError, TypeError):
        return {"ok": False, "reason": "artifact_write_failed"}


def load_verified_result(*, cfg: Config, repo: str, pr: int, head_sha: str, artifact_sha256: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    if not _SHA.fullmatch(str(head_sha or "").lower()) or not _HASH.fullmatch(str(artifact_sha256 or "")):
        return None
    directory = Path(cfg.pr_review_artifacts_dir).expanduser().resolve() / "results" / _safe_component(repo) / str(int(pr))
    try:
        path, = directory.glob(f"{head_sha.lower()}-{artifact_sha256}.json")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != artifact_sha256:
            return None
        payload = json.loads(raw)
    except (OSError, ValueError, TypeError):
        return None
    expected = {"schema":"lokay.review-artifact/1", "repo":repo, "pr":int(pr), "head_sha":head_sha.lower(), "review_config_sha256":str(cfg.pr_review_config_sha256)}
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in expected.items()):
        return None
    if evidence is not None and any(payload.get(key) != evidence.get(key) for key in ("base_ref_sha", "comparison_base_sha", "diff_sha256", "task_identity_sha256")):
        return None
    task = evidence.get("task") if evidence is not None else None
    if not isinstance(task, dict) or not task:
        return None
    task_digest = hashlib.sha256(_canonical(task)).hexdigest()
    if task_digest != payload.get("task_identity_sha256"):
        return None
    execution = evidence.get("review_execution") if evidence is not None else None
    decision = payload.get("decision")
    if not isinstance(decision, Mapping):
        return None
    if execution is not None:
        if not isinstance(execution, Mapping) or any(
            payload.get(key) != execution.get(source)
            for key, source in (
                ("preview_sha256", "preview_sha256"),
                ("input_fingerprint_sha256", "input_fingerprint_sha256"),
                ("upstream_rule_config_sha256", "rule_config_sha256"),
                ("upstream_runtime_config_sha256", "runtime_config_sha256"),
            )
        ):
            return None
    if evidence is not None and any(
        payload.get(key) != evidence.get(key)
        for key in ("head_ref", "head_repo", "base_ref", "diff_paths", "changed_ranges")
    ):
        return None
    engine = payload.get("engine")
    if not isinstance(engine, dict) or any(engine.get(key) != expected for key, expected in {
        "version":cfg.pr_review_binary_version, "binary_sha256":cfg.pr_review_binary_sha256,
        "provider":cfg.pr_review_provider, "model":cfg.pr_review_model,
    }.items()):
        return None
    return {
        **payload,
        "decision": {**payload["decision"], "task": task},
    }
