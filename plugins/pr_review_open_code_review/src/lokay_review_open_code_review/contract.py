"""Versioned, vendor-neutral review result contract."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "lokay.review-result/1"
MANIFEST_SCHEMA = "ocr.run-manifest/v1"
ENGINE_VERSION = "v1.12.0"
CATEGORIES = frozenset(
    {
        "bug",
        "security",
        "performance",
        "maintainability",
        "test",
        "style",
        "documentation",
        "other",
    }
)
SEVERITIES = frozenset({"critical", "high", "medium", "low"})
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Untrusted upstream output failed the pinned neutral contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _required_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _digest(value: Any, name: str) -> str:
    text = str(value or "").lower()
    if not _HASH_RE.fullmatch(text):
        raise ContractError(f"{name} must be a SHA-256 digest")
    return text


def _sha(value: Any, name: str) -> str:
    text = str(value or "").lower()
    if not _SHA_RE.fullmatch(text):
        raise ContractError(f"{name} must be a full commit SHA")
    return text


def _path(value: Any, name: str) -> str:
    text = str(value or "")
    if not text or text.startswith("/") or "\\" in text or "\x00" in text:
        raise ContractError(f"invalid {name}")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ContractError(f"invalid {name}")
    return text


def _path_identity(row: Mapping[str, Any]) -> tuple[str, str]:
    path = _path(row.get("path"), "coverage path")
    old_path = str(row.get("old_path") or "")
    if old_path:
        old_path = _path(old_path, "old coverage path")
    return path, old_path


def _path_rows(value: Any, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ContractError(f"{name} must be an array")
    rows = [_required_mapping(item, f"{name}[]") for item in value]
    identities = [_path_identity(row) for row in rows]
    if len(set(identities)) != len(identities):
        raise ContractError(f"duplicate {name} identity")
    return rows


def _coverage_item(row: Mapping[str, Any]) -> dict[str, str]:
    path, old_path = _path_identity(row)
    return {"path": path, "old_path": old_path}


def validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the public Lokay request before any engine calls."""
    if request.get("schema") != "lokay.review-request/1":
        raise ContractError("unknown review request schema")
    repo = str(request.get("repo") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ContractError("invalid repository identity")
    pr = request.get("pr")
    if not isinstance(pr, int) or isinstance(pr, bool) or pr < 1:
        raise ContractError("invalid PR number")
    task = _required_mapping(request.get("task"), "task")
    if (
        task.get("repo") != repo
        or task.get("type") != "Issue"
        or task.get("state") != "OPEN"
        or not isinstance(task.get("number"), int)
        or isinstance(task.get("number"), bool)
        or task.get("number", 0) < 1
        or not str(task.get("title") or "").strip()
        or not isinstance(task.get("body"), str)
        or not str(task.get("url") or "").strip()
    ):
        raise ContractError("canonical OPEN Issue task is required")
    task_fields = {
        key: task[key]
        for key in ("repo", "type", "state", "number", "title", "body", "url")
    }
    task_digest = _digest(request.get("task_identity_sha256"), "task identity")
    if sha256_json(task_fields) != task_digest:
        raise ContractError("task identity digest mismatch")
    diff_sha = _digest(request.get("diff_sha256"), "diff")
    head = _sha(request.get("head_sha"), "head SHA")
    base_ref = _sha(request.get("base_ref_sha"), "base ref SHA")
    comparison_base = _sha(request.get("comparison_base_sha"), "comparison base SHA")
    if task.get("number") == pr:
        raise ContractError("task Issue number collides with PR number; canonical Issue proof is required")
    repo_path = str(request.get("repo_path") or "")
    if not repo_path:
        raise ContractError("repository checkout path required")
    head_ref_name = str(request.get("head_ref") or "")
    base_ref_name = str(request.get("base_ref") or "")
    head_repo = str(request.get("head_repo") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repo):
        raise ContractError("canonical PR head repository identity is required")
    if not head_ref_name or not base_ref_name:
        raise ContractError("PR base/head branch refs are required")
    if request.get("review_config_sha256") is not None:
        _digest(request.get("review_config_sha256"), "review configuration")
    ranges = request.get("changed_ranges")
    if not isinstance(ranges, Mapping):
        raise ContractError("changed-line ranges are required")
    diff_paths = _path_rows(request.get("diff_paths"), "diff paths")
    if not diff_paths:
        raise ContractError("empty diff cannot be approved")
    allowed = {"added", "modified", "deleted", "renamed", "copied", "type_changed"}
    for row in diff_paths:
        if str(row.get("status") or "") not in allowed:
            raise ContractError("unknown diff path status")
    return {
        "repo": repo,
        "pr": pr,
        "head_ref": head_ref_name,
        "head_repo": head_repo,
        "base_ref": base_ref_name,
        "head_sha": head,
        "base_ref_sha": base_ref,
        "comparison_base_sha": comparison_base,
        "task_identity_sha256": task_digest,
        "diff_sha256": diff_sha,
        "diff_paths": diff_paths,
        "repo_path": repo_path,
        "head_ref": head_ref_name,
        "base_ref": base_ref_name,
        "head_repo": head_repo,
        "changed_ranges": dict(ranges),
    }


def _validate_preview(preview: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    files = preview.get("files")
    if not isinstance(files, list) or not files:
        raise ContractError("preview is incomplete or empty")
    total_files = preview.get("total_files")
    if not isinstance(total_files, int) or isinstance(total_files, bool) or total_files != len(files):
        raise ContractError("preview total_files does not match file entries")
    reviewable_count = preview.get("reviewable_count")
    excluded_count = preview.get("excluded_count")
    if reviewable_count != sum(bool(row.get("will_review")) for row in files if isinstance(row, Mapping)):
        raise ContractError("preview reviewable count mismatch")
    if excluded_count != sum(not bool(row.get("will_review")) for row in files if isinstance(row, Mapping)):
        raise ContractError("preview excluded count mismatch")
    inventory = {_path_identity(row): row for row in request["diff_paths"]}
    if len(inventory) != len(request["diff_paths"]):
        raise ContractError("ambiguous Lokay diff path identity")
    joined: dict[str, Mapping[str, Any]] = {}
    reviewable: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in files:
        row = _required_mapping(item, "preview file")
        path = _path(row.get("path"), "preview path")
        status = str(row.get("status") or "")
        candidates = [
            (identity, source)
            for identity, source in inventory.items()
            if identity[0] == path and str(source.get("status") or "") == status
        ]
        if len(candidates) != 1:
            raise ContractError("preview path does not uniquely match Lokay diff")
        identity, source = candidates[0]
        if identity in seen:
            raise ContractError("duplicate preview path identity")
        seen.add(identity)
        joined[path] = source
        if bool(row.get("will_review")):
            if row.get("exclude_reason") not in (None, ""):
                raise ContractError("reviewable preview entry has exclusion reason")
            reviewable.append({**_coverage_item(source), "status": status})
        else:
            reason = str(row.get("exclude_reason") or "")
            if status != "deleted" or reason != "deleted" or identity[1]:
                raise ContractError("preview contains excluded in-scope paths")
            excluded.append({**_coverage_item(source), "status": status})
    if seen != set(inventory):
        raise ContractError("preview does not cover the complete Lokay diff")
    if not reviewable:
        raise ContractError("empty reviewable preview cannot be approved")
    return reviewable, excluded, [{"path": path, "old_path": old} for path, old in sorted(seen)]


def _manifest_coverage(manifest: Mapping[str, Any], reviewable: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    coverage = _required_mapping(manifest.get("coverage"), "manifest coverage")
    selected_rows = _path_rows(coverage.get("selected"), "coverage.selected")
    completed_rows = _path_rows(coverage.get("completed"), "coverage.completed")
    reused_rows = _path_rows(coverage.get("reused"), "coverage.reused")
    failed_rows = _path_rows(coverage.get("failed"), "coverage.failed")
    waived_rows = _path_rows(coverage.get("waived"), "coverage.waived")
    selected = {_path_identity(row) for row in selected_rows}
    completed = {_path_identity(row) for row in completed_rows}
    expected = {(row["path"], row["old_path"]) for row in reviewable}
    if selected != expected:
        raise ContractError("coverage selected does not match reviewable preview")
    if completed != selected or reused_rows or failed_rows or waived_rows:
        raise ContractError("coverage is incomplete or contains non-complete states")
    return {
        "selected": sorted((_coverage_item(row) for row in selected_rows), key=lambda x: (x["path"], x["old_path"])),
        "completed": sorted((_coverage_item(row) for row in completed_rows), key=lambda x: (x["path"], x["old_path"])),
        "reused": [],
        "failed": [],
        "waived": [],
    }


def normalize_result(
    request: Mapping[str, Any],
    preview: Mapping[str, Any],
    upstream: Mapping[str, Any],
    *,
    engine: Mapping[str, Any],
    changed_ranges: Mapping[str, list[tuple[int, int]]],
) -> dict[str, Any]:
    """Validate pinned v1.12 preview/run evidence and map to neutral JSON."""
    normalized_request = validate_request(request)
    _required_mapping(preview, "preview")
    _required_mapping(upstream, "review output")
    _required_mapping(engine, "engine config")
    if engine.get("version") != ENGINE_VERSION:
        raise ContractError("unexpected pinned engine version")
    engine_hash = _digest(engine.get("binary_sha256"), "engine binary")
    if engine_hash != _digest(request.get("engine", {}).get("binary_sha256"), "request engine binary"):
        raise ContractError("engine binary digest does not match request")
    if request.get("review_config_sha256") != engine.get("config_sha256"):
        raise ContractError("review configuration digest does not match request")
    expected_origin = f"github.com/{normalized_request['repo']}"
    origin_sha = hashlib.sha256(expected_origin.encode("utf-8")).hexdigest()
    config_hash = _digest(engine.get("config_sha256"), "review configuration")
    reviewable, excluded, inventory = _validate_preview(preview, normalized_request)
    if not isinstance(upstream.get("comments"), list):
        raise ContractError("review comments array is required")
    manifest = _required_mapping(upstream.get("manifest"), "run manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ContractError("unknown run manifest schema")
    if manifest.get("operation") != "review":
        raise ContractError("manifest operation mismatch")
    if manifest.get("terminal_state") != "complete" or upstream.get("status") != "complete":
        raise ContractError("review terminal state is not complete")
    if manifest.get("run_failure") not in (None, {}):
        raise ContractError("manifest run_failure is present")
    repository = _required_mapping(manifest.get("repository"), "manifest repository")
    if repository.get("identity_sha256") != origin_sha:
        raise ContractError("repository origin identity mismatch")
    input_info = _required_mapping(manifest.get("input"), "manifest input")
    if input_info.get("mode") != "range":
        raise ContractError("manifest input mode must be range")
    expected_refs = {
        "requested_from": normalized_request["base_ref_sha"],
        "requested_head": normalized_request["head_sha"],
        "resolved_base": normalized_request["comparison_base_sha"],
        "resolved_head": normalized_request["head_sha"],
        "exact_range": f"{normalized_request['comparison_base_sha']}..{normalized_request['head_sha']}",
    }
    for key, expected in expected_refs.items():
        if input_info.get(key) != expected:
            raise ContractError(f"manifest {key} mismatch")
    execution = _required_mapping(manifest.get("execution"), "manifest execution")
    upstream_llm = _required_mapping(upstream.get("llm"), "review LLM identity")
    if (
        execution.get("ocr_version") != ENGINE_VERSION
        or execution.get("provider") != engine.get("provider")
        or execution.get("model") != engine.get("model")
        or execution.get("configured_concurrency") != 1
        or upstream_llm.get("provider") != engine.get("provider")
        or upstream_llm.get("model") != engine.get("model")
    ):
        raise ContractError("upstream execution identity mismatch")
    rule_hash = _digest(execution.get("rule_config_sha256"), "rule config")
    runtime_hash = _digest(execution.get("runtime_config_sha256"), "runtime config")
    if not isinstance(upstream.get("warnings"), list) or upstream.get("warnings"):
        raise ContractError("review has warnings")
    if "thinking" in upstream:
        raise ContractError("raw reasoning is not accepted at the review boundary")
    summary = _required_mapping(upstream.get("summary"), "review summary")
    if summary.get("budget_exceeded") is not False:
        raise ContractError("review budget exceeded or unreported")
    tool_calls = _required_mapping(upstream.get("tool_calls"), "tool call summary")
    if tool_calls.get("failure") != 0:
        raise ContractError("review tool failure")
    coverage = _manifest_coverage(manifest, reviewable)
    comments = upstream["comments"]
    findings: list[dict[str, Any]] = []
    valid_by_path: dict[str, list[tuple[int, int]]] = {}
    for item in comments:
        comment = _required_mapping(item, "review finding")
        if "thinking" in comment:
            # It is discarded, never forwarded or persisted.
            pass
        path = _path(comment.get("path"), "finding path")
        matches = [row for row in reviewable if row["path"] == path]
        if len(matches) != 1:
            raise ContractError("finding path is outside reviewed diff")
        start, end = comment.get("start_line"), comment.get("end_line")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 1
            or end < start
        ):
            raise ContractError("invalid finding line range")
        category = str(comment.get("category") or "")
        severity = str(comment.get("severity") or "")
        if category not in CATEGORIES or severity not in SEVERITIES:
            raise ContractError("unknown finding category or severity")
        content = str(comment.get("content") or "")
        if not content.strip():
            raise ContractError("finding content is required")
        ranges = changed_ranges.get(path)
        if not isinstance(ranges, list) or not any(
            isinstance(bounds, (tuple, list))
            and len(bounds) == 2
            and bounds[0] <= start
            and end <= bounds[1]
            for bounds in ranges
        ):
            raise ContractError("finding anchor is not within changed lines")
        valid_by_path.setdefault(path, []).append((start, end))
        findings.append(
            {
                "path": path,
                "start_line": start,
                "end_line": end,
                "category": category,
                "severity": severity,
                "content": content,
                "existing_code": str(comment.get("existing_code") or ""),
                "suggestion_code": str(comment.get("suggestion_code") or ""),
            }
        )
    for finding in findings:
        valid = valid_by_path[finding["path"]]
        if not any(start <= finding["start_line"] <= end for start, end in valid):
            raise ContractError("invalid finding anchor")
    identity = sha256_json(
        {
            "repo": normalized_request["repo"],
            "pr": normalized_request["pr"],
            "head_sha": normalized_request["head_sha"],
            "base_ref_sha": normalized_request["base_ref_sha"],
            "comparison_base_sha": normalized_request["comparison_base_sha"],
            "task_identity_sha256": normalized_request["task_identity_sha256"],
            "diff_sha256": normalized_request["diff_sha256"],
            "engine": {key: engine[key] for key in ("name", "version", "binary_sha256", "provider", "model")},
            "review_config_sha256": config_hash,
            "execution": {
                "rule_config_sha256": rule_hash,
                "runtime_config_sha256": runtime_hash,
            },
        }
    )
    neutral_evidence = {
        "manifest_schema": MANIFEST_SCHEMA,
        "operation": "review",
        "input_mode": "range",
        **expected_refs,
        "resolved_base_sha": normalized_request["comparison_base_sha"],
        "resolved_head_sha": normalized_request["head_sha"],
        "terminal_state": "complete",
        "run_failure": None,
        "warning_count": 0,
        "tool_failure_count": 0,
        "budget_exceeded": False,
        "upstream_execution": {
            "ocr_version": ENGINE_VERSION,
            "provider": str(execution.get("provider")),
            "model": str(execution.get("model")),
            "configured_concurrency": 1,
            "rule_config_sha256": rule_hash,
            "runtime_config_sha256": runtime_hash,
        },
        "repository_identity_sha256": origin_sha,
        "preview_sha256": sha256_json(dict(preview)),
        "input_fingerprint_sha256": identity,
    }
    return {
        "ok": True,
        "schema": SCHEMA,
        "engine": {
            "name": "open-code-review",
            "version": ENGINE_VERSION,
            "binary_sha256": engine_hash,
            "provider": str(engine.get("provider") or ""),
            "model": str(engine.get("model") or ""),
            "config_sha256": config_hash,
        },
        "repo": normalized_request["repo"],
        "pr": normalized_request["pr"],
        "head_ref": normalized_request["head_ref"],
        "head_repo": normalized_request["head_repo"],
        "base_ref": normalized_request["base_ref"],
        "head_sha": normalized_request["head_sha"],
        "base_ref_sha": normalized_request["base_ref_sha"],
        "comparison_base_sha": normalized_request["comparison_base_sha"],
        "task_identity_sha256": normalized_request["task_identity_sha256"],
        "diff_sha256": normalized_request["diff_sha256"],
        "diff_paths": normalized_request["diff_paths"],
        "status": "complete",
        "findings": findings,
        "summary": "Review complete; findings block until repaired." if findings else "Review complete with no findings.",
        "evidence": neutral_evidence,
        "coverage": {
            "diff_paths": inventory,
            "reviewable_paths": reviewable,
            "selected": coverage["selected"],
            "completed": coverage["completed"],
            "reused": coverage["reused"],
            "failed": coverage["failed"],
            "waived": coverage["waived"],
            "excluded": excluded,
        },
    }
