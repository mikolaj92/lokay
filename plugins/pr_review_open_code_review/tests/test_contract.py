from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from lokay_review_open_code_review.contract import (  # noqa: E402
    ContractError,
    normalize_result,
    sha256_json,
)

FIXTURES = Path(__file__).parent / "fixtures" / "upstream_v1_12"


def _request() -> dict:
    task = {
        "repo": "acme/demo",
        "type": "Issue",
        "state": "OPEN",
        "number": 42,
        "title": "Prevent invalid save",
        "body": "Acceptance: reject blank IDs.",
        "url": "https://github.com/acme/demo/issues/42",
    }
    return {
        "schema": "lokay.review-request/1",
        "repo": "acme/demo",
        "pr": 84,
        "head_ref": "ai/fix/42-demo",
        "head_sha": "b" * 40,
        "base_ref": "main",
        "head_repo": "acme/demo",
        "base_ref_sha": "a" * 40,
        "comparison_base_sha": "c" * 40,
        "repo_path": "/tmp/review-checkout",
        "changed_ranges": {"src/demo.py": [(12, 13)]},
        "review_config_sha256": "9" * 64,
        "diff_paths": [
            {"path": "src/demo.py", "old_path": "", "status": "modified"}
        ],
        "diff_sha256": "d" * 64,
        "pr_title": "Fix demo flow",
        "pr_body": "PR description is not canonical task evidence.",
        "task": task,
        "task_identity_sha256": sha256_json(task),
        "engine": {"binary_sha256": "f" * 64, "config_sha256": "9" * 64},
    }


def _upstream() -> tuple[dict, dict]:
    return (
        json.loads((FIXTURES / "preview-complete.json").read_text()),
        json.loads((FIXTURES / "review-complete.json").read_text()),
    )


def _engine() -> dict:
    return {
        "name": "open-code-review",
        "version": "v1.12.0",
        "binary_sha256": "f" * 64,
        "provider": "example-provider",
        "model": "example-model",
        "config_sha256": "9" * 64,
    }


def _normalize(request: dict | None = None, preview: dict | None = None, upstream: dict | None = None) -> dict:
    default_preview, default_upstream = _upstream()
    return normalize_result(
        request or _request(),
        preview or default_preview,
        upstream or default_upstream,
        engine=_engine(),
        changed_ranges={"src/demo.py": [(12, 13)], "src/new.py": [(12, 13)]},
    )


def test_v112_result_maps_to_closed_lokay_contract_without_thinking():
    result = _normalize()

    assert result["ok"] is True
    assert result["schema"] == "lokay.review-result/1"
    assert result["head_sha"] == "b" * 40
    assert result["base_ref_sha"] == "a" * 40
    assert result["comparison_base_sha"] == "c" * 40
    assert result["task_identity_sha256"] == _request()["task_identity_sha256"]
    assert result["diff_sha256"] == "d" * 64
    assert result["status"] == "complete"
    assert result["findings"] == [
        {
            "path": "src/demo.py",
            "start_line": 12,
            "end_line": 13,
            "category": "bug",
            "severity": "high",
            "content": "Blank IDs reach persistence.",
            "existing_code": "save(record)",
            "suggestion_code": "if not record.id:\n    return False",
        }
    ]
    assert "thinking" not in json.dumps(result)
    assert result["coverage"]["selected"] == [
        {"path": "src/demo.py", "old_path": ""}
    ]
    assert result["coverage"]["completed"] == result["coverage"]["selected"]
    assert result["coverage"]["failed"] == []
    assert result["coverage"]["waived"] == []
    assert result["evidence"]["manifest_schema"] == "ocr.run-manifest/v1"
    assert result["evidence"]["requested_from"] == "a" * 40
    assert result["evidence"]["resolved_base_sha"] == "c" * 40
    assert len(result["evidence"]["preview_sha256"]) == 64
    assert len(result["evidence"]["input_fingerprint_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda preview, run: run.update(status="partial"), "terminal"),
        (lambda preview, run: run["manifest"].update(terminal_state="partial"), "terminal"),
        (lambda preview, run: run["manifest"].update(run_failure={"classification": "budget"}), "run_failure"),
        (lambda preview, run: run["summary"].update(budget_exceeded=True), "budget"),
        (lambda preview, run: run["tool_calls"].update(failure=1), "tool failure"),
        (lambda preview, run: run.update(warnings=[{"message": "do not expose"}]), "warning"),
        (lambda preview, run: run["manifest"]["coverage"].update(failed=[{"path": "src/demo.py"}]), "coverage"),
        (lambda preview, run: run["manifest"]["coverage"].update(waived=[{"path": "src/demo.py"}]), "coverage"),
        (lambda preview, run: (preview["files"][0].update(will_review=False, exclude_reason="too_large"), preview.update(reviewable_count=0, excluded_count=1)), "excluded"),
        (lambda preview, run: run["manifest"].pop("coverage"), "coverage"),
        (lambda preview, run: run["manifest"]["coverage"]["completed"].clear(), "coverage"),
        (lambda preview, run: run["manifest"]["input"].update(requested_from="0" * 40), "requested_from"),
        (lambda preview, run: run["manifest"]["execution"].update(configured_concurrency=2), "execution identity"),
    ],
)
def test_incomplete_or_inconsistent_upstream_evidence_fails_closed(mutate, match):
    preview, upstream = _upstream()
    mutate(preview, upstream)

    with pytest.raises(ContractError, match=match):
        _normalize(preview=preview, upstream=upstream)


def test_rename_coverage_keeps_old_and_new_path_identity():
    request = _request()
    request["diff_paths"] = [
        {"path": "src/new.py", "old_path": "src/old.py", "status": "renamed"}
    ]
    preview, upstream = _upstream()
    preview["files"][0].update(path="src/new.py", status="renamed")
    upstream["manifest"]["coverage"]["selected"][0].update(
        path="src/new.py", old_path="src/old.py"
    )
    upstream["manifest"]["coverage"]["completed"][0].update(
        path="src/new.py", old_path="src/old.py"
    )
    upstream["comments"][0]["path"] = "src/new.py"

    result = _normalize(request, preview, upstream)

    assert result["coverage"]["reviewable_paths"] == [
        {"path": "src/new.py", "old_path": "src/old.py", "status": "renamed"}
    ]


def test_delete_is_explicitly_excluded_but_other_exclusions_fail():
    request = _request()
    request["diff_paths"].append(
        {"path": "src/removed.py", "old_path": "", "status": "deleted"}
    )
    preview, upstream = _upstream()
    preview["files"].append(
        {
            "path": "src/removed.py",
            "status": "deleted",
            "insertions": 0,
            "deletions": 3,
            "will_review": False,
            "exclude_reason": "deleted",
        }
    )
    preview["total_files"] = 2
    preview["reviewable_count"] = 1
    preview["excluded_count"] = 1

    result = _normalize(request, preview, upstream)
    assert result["coverage"]["excluded"] == [
        {"path": "src/removed.py", "old_path": "", "status": "deleted"}
    ]

    preview["files"][1]["exclude_reason"] = "too_large"
    with pytest.raises(ContractError, match="excluded"):
        _normalize(request, preview, upstream)


def test_low_severity_findings_remain_findings():
    preview, upstream = _upstream()
    upstream["comments"][0]["severity"] = "low"

    result = _normalize(preview=preview, upstream=upstream)

    assert result["findings"][0]["severity"] == "low"
    assert len(result["findings"]) == 1


def test_omitted_vendor_warnings_are_empty_not_rejected():
    preview, upstream = _upstream()
    upstream.pop("warnings")

    result = _normalize(preview=preview, upstream=upstream)

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["evidence"]["warning_count"] == 0


def test_operational_ocr_nits_do_not_fail_closed():
    preview, upstream = _upstream()
    upstream["warnings"] = [
        {
            "type": "comment_refiled",
            "file": "src/demo.py",
            "message": "comment filed against src/old.py describes code in src/demo.py; re-filed",
        },
        {
            "type": "comment_args_repaired",
            "file": "src/demo.py",
            "message": "comments violated the array schema",
        },
    ]

    result = _normalize(preview=preview, upstream=upstream)

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["findings"]
    assert result["evidence"]["warning_count"] == 0


@pytest.mark.parametrize(
    "warning",
    [
        {"type": "token_budget_reached", "file": "src/demo.py", "message": "budget"},
        {"type": "manifest_error", "file": "", "message": "cannot freeze"},
        {"type": "review_round_failed", "file": "src/demo.py", "message": "round 1"},
        {"type": "token_threshold_exceeded", "file": "src/demo.py", "message": "tokens"},
        {"type": "unknown_vendor_signal", "file": "src/demo.py", "message": "new"},
    ],
)
def test_material_ocr_warnings_fail_closed_and_keep_type(warning):
    preview, upstream = _upstream()
    upstream["warnings"] = [warning]

    with pytest.raises(ContractError, match="warning") as caught:
        _normalize(preview=preview, upstream=upstream)
    assert caught.value.warnings == [{"type": warning["type"], "file": warning["file"]}]
