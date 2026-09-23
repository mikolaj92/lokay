"""Validate a complete neutral review-result envelope and select Lokay policy."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err, ok

_SCHEMA = "lokay.review-result/1"


def _path_identity(row: Mapping[str, Any]) -> tuple[str, str]:
    """Host-owned neutral path identity; no vendor imports."""
    path, old = row.get("path"), row.get("old_path", "")
    for value in (path, old):
        if not isinstance(value, str) or "\\" in value or "\x00" in value:
            raise ValueError("invalid coverage path")
        if value and any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError("invalid coverage path")
    if not path:
        raise ValueError("missing coverage path")
    return path, old


def validate_result(result: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("ok") is not True or result.get("schema") != _SCHEMA:
        return err("unknown or unsuccessful review result", route="fail_closed")
    identities = (
        "repo", "pr", "head_ref", "head_repo", "base_ref", "head_sha", "base_ref_sha", "comparison_base_sha",
        "task_identity_sha256", "diff_sha256",
    )
    if any(result.get(key) != request.get(key) for key in identities):
        return err("review result identity drift", route="fail_closed")
    if result.get("diff_paths") != request.get("diff_paths"):
        return err("review result path inventory drift", route="fail_closed")
    engine = result.get("engine")
    requested_engine = request.get("engine")
    if not isinstance(engine, Mapping) or not isinstance(requested_engine, Mapping):
        return err("review engine identity is missing", route="fail_closed")
    if (
        engine.get("binary_sha256") != requested_engine.get("binary_sha256")
        or engine.get("provider") != requested_engine.get("provider")
        or engine.get("model") != requested_engine.get("model")
        or engine.get("config_sha256") != request.get("review_config_sha256")
    ):
        return err("review engine identity drift", route="fail_closed")
    if result.get("status") != "complete" or not isinstance(result.get("findings"), list):
        return err("review result is incomplete", route="fail_closed")
    has_findings = bool(result["findings"])
    evidence = result.get("evidence")
    coverage = result.get("coverage")
    task = request.get("task")
    if not isinstance(task, Mapping) or not task:
        return err("canonical review task is missing", route="fail_closed")
    canonical_task = {
        "repo": task.get("repo"),
        "type": task.get("type"),
        "state": task.get("state"),
        "number": task.get("number"),
        "title": task.get("title"),
        "body": task.get("body"),
        "url": task.get("url"),
    }
    task_digest = __import__("hashlib").sha256(
        json.dumps(
            canonical_task, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    if (
        canonical_task["repo"] != request.get("repo")
        or canonical_task["type"] != "Issue"
        or canonical_task["state"] != "OPEN"
        or canonical_task["number"] is None
        or not isinstance(canonical_task["title"], str)
        or not isinstance(canonical_task["body"], str)
        or not isinstance(canonical_task["url"], str)
        or task_digest != request.get("task_identity_sha256")
    ):
        return err("canonical review task identity is invalid", route="fail_closed")
    if not isinstance(evidence, Mapping) or not isinstance(coverage, Mapping):
        return err("review evidence or coverage is missing", route="fail_closed")
    if (
        not isinstance(evidence.get("manifest_schema"), str)
        or not evidence.get("manifest_schema")
        or evidence.get("tool_failure_count") != 0
        or evidence.get("resolved_head_sha") != request.get("head_sha")
        or evidence.get("resolved_base_sha") != request.get("comparison_base_sha")
        or evidence.get("requested_from") != request.get("base_ref_sha")
        or evidence.get("requested_head") != request.get("head_sha")
        or evidence.get("repository_identity_sha256") != __import__("hashlib").sha256(
            f"github.com/{request.get('repo')}".encode("utf-8")
        ).hexdigest()
        or not isinstance(evidence.get("preview_sha256"), str)
        or not __import__("re").fullmatch(r"[a-f0-9]{64}", str(evidence.get("preview_sha256") or ""))
        or not isinstance(evidence.get("input_fingerprint_sha256"), str)
        or not __import__("re").fullmatch(r"[a-f0-9]{64}", str(evidence.get("input_fingerprint_sha256") or ""))
        or evidence.get("exact_range") != f"{request.get('comparison_base_sha')}..{request.get('head_sha')}"
        or evidence.get("operation") != "review"
        or evidence.get("input_mode") != "range"
    ):
        return err("review evidence is incomplete or inconsistent", route="fail_closed")
    warnings = evidence.get("warnings", [])
    if not has_findings and (
        evidence.get("terminal_state") != "complete"
        or evidence.get("upstream_status", "complete") != "complete"
        or evidence.get("run_failure") not in (None, {})
        or evidence.get("budget_exceeded") is not False
        or not isinstance(warnings, list)
        or evidence.get("warning_count") != len(warnings)
        or any(not isinstance(w, Mapping) or w.get("type") not in {
            "comment_refiled", "comment_args_repaired"
        } for w in warnings)
    ):
        return err("review execution is incomplete", route="fail_closed")
    paths = coverage.get("reviewable_paths")
    selected, completed = coverage.get("selected"), coverage.get("completed")
    if (
        not isinstance(paths, list) or not paths
        or not isinstance(selected, list) or not isinstance(completed, list)
        or any(not isinstance(coverage.get(key), list) for key in ("failed", "waived", "reused"))
    ):
        return err("review coverage is incomplete", route="fail_closed")
    try:
        selected_set = {_path_identity(row) for row in selected if isinstance(row, Mapping)}
        completed_set = {_path_identity(row) for row in completed if isinstance(row, Mapping)}
        expected_set = {_path_identity(row) for row in paths if isinstance(row, Mapping)}
        if not selected_set or not selected_set.issubset(expected_set):
            return err("review coverage identity sets are inconsistent", route="fail_closed")
        for key in ("selected", "completed", "failed", "waived", "reused"):
            rows = coverage[key]
            identities = {_path_identity(row) for row in rows if isinstance(row, Mapping)}
            if len(identities) != len(rows) or not identities.issubset(selected_set):
                return err("review coverage identity sets are inconsistent", route="fail_closed")
        if not has_findings and (
            selected_set != completed_set or selected_set != expected_set
            or any(coverage[key] for key in ("failed", "waived", "reused"))
        ):
            return err("review coverage is incomplete", route="fail_closed")
    except (TypeError, ValueError):
        return err("review coverage identities are malformed", route="fail_closed")
    normalized_findings: list[dict[str, Any]] = []
    allowed = {(row.get("path"), row.get("old_path", "")) for row in paths if isinstance(row, Mapping)}
    inventory = {
        (row.get("path"), row.get("old_path", ""), row.get("status"))
        for row in request.get("diff_paths", []) if isinstance(row, Mapping)
    }
    expected_reviewable = {
        (path, old_path, status)
        for path, old_path, status in inventory
        if status != "deleted"
    }
    actual_reviewable = {
        (row.get("path"), row.get("old_path", ""), row.get("status"))
        for row in paths if isinstance(row, Mapping)
    }
    if actual_reviewable != expected_reviewable:
        return err("reviewable path inventory does not match exact Lokay diff", route="fail_closed")
    excluded = coverage.get("excluded")
    expected_excluded = {
        (path, old_path, status)
        for path, old_path, status in inventory if status == "deleted"
    }
    if not isinstance(excluded, list) or {
        (row.get("path"), row.get("old_path", ""), row.get("status"))
        for row in excluded if isinstance(row, Mapping)
    } != expected_excluded:
        return err("excluded paths do not match deleted-only diff scope", route="fail_closed")
    changed = request.get("changed_ranges") if isinstance(request.get("changed_ranges"), Mapping) else {}
    for raw in result["findings"]:
        if not isinstance(raw, Mapping):
            return err("malformed finding", route="fail_closed")
        path = str(raw.get("path") or "")
        start, end = raw.get("start_line"), raw.get("end_line")
        if sum(candidate == path for candidate, _old in allowed) != 1 or not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start:
            return err("finding anchor is malformed", route="fail_closed")
        if not any(
            isinstance(bounds, (list, tuple)) and len(bounds) == 2 and bounds[0] <= start and end <= bounds[1]
            for bounds in changed.get(path, [])
        ):
            return err("finding is not anchored to changed lines", route="fail_closed")
        if raw.get("severity") not in {"critical", "high", "medium", "low"}:
            return err("unknown finding severity", route="fail_closed")
        if raw.get("category") not in {"bug", "security", "performance", "maintainability", "test", "style", "documentation", "other"}:
            return err("unknown finding category", route="fail_closed")
        if not str(raw.get("content") or "").strip():
            return err("finding content is missing", route="fail_closed")
        normalized_findings.append({key: raw.get(key, "") for key in (
            "path", "start_line", "end_line", "category", "severity", "content",
            "existing_code", "suggestion_code",
        )})
    input_fingerprint = str(evidence.get("input_fingerprint_sha256") or "")
    if not __import__("re").fullmatch(r"[a-f0-9]{64}", input_fingerprint):
        return err("review input fingerprint is missing", route="fail_closed")
    execution = evidence.get("upstream_execution")
    if not isinstance(execution, Mapping):
        return err("upstream execution identity is missing", route="fail_closed")
    for key in ("rule_config_sha256", "runtime_config_sha256"):
        if not __import__("re").fullmatch(r"[a-f0-9]{64}", str(execution.get(key) or "")):
            return err("upstream config identity is malformed", route="fail_closed")
    decision = {
        "verdict": "request_changes" if normalized_findings else "approve",
        "risk": "medium",
        "scope_ok": True,
        "secrets": any(row["category"] == "security" for row in normalized_findings),
        "tests_adequate": True,
        "blocking": [f"{row['path']}:{row['start_line']}-{row['end_line']} [{row['severity']}] {row['content']}" for row in normalized_findings],
        "evidence_kind": None,
        "nits": [],
        "summary": str(result.get("summary") or "Review complete."),
        "findings": normalized_findings,
        "review_evidence": dict(evidence),
        "review_coverage": dict(coverage),
        "reviewed_head_sha": request["head_sha"],
        "task": request.get("task"),
        "task_identity_sha256": request.get("task_identity_sha256"),
        "review_input_fingerprint_sha256": input_fingerprint,
        "review_preview_sha256": str(evidence.get("preview_sha256") or ""),
        "review_rule_config_sha256": str(execution.get("rule_config_sha256") or ""),
        "review_runtime_config_sha256": str(execution.get("runtime_config_sha256") or ""),
        "review_result_sha256": __import__("hashlib").sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    return ok(route="valid", decision=decision)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-validate-pr-review")
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args(argv)
    try:
        result, request = json.loads(args.result_json), json.loads(args.request_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid review validation JSON: {exc}"))
    if not isinstance(result, dict) or not isinstance(request, dict):
        return emit_exit(err("review result and request objects required"))
    return emit_exit(validate_result(result, request))


if __name__ == "__main__":
    raise SystemExit(main())
