from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc.pr_review_artifacts import load_verified_result, persist_result


def _inputs(root: Path):
    task = {
        "repo": "acme/demo", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "Acceptance criteria", "url": "https://github.com/acme/demo/issues/42",
    }
    task_digest = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    cfg = SimpleNamespace(
        pr_review_artifacts_dir=root, pr_review_config_sha256="9" * 64,
        pr_review_binary_version="v1.12.0", pr_review_binary_sha256="f" * 64,
        pr_review_provider="p", pr_review_model="m",
    )
    evidence = {
        "head_ref": "ai/fix/42-task", "head_repo": "acme/demo", "base_ref": "main",
        "diff_paths": [{"path":"src/a.py", "old_path":"", "status":"modified"}],
        "changed_ranges": {"src/a.py":[[1,1]]},
        "head_sha": "b" * 40, "base_ref_sha": "a" * 40,
        "comparison_base_sha": "c" * 40, "diff_sha256": "d" * 64,
        "task_identity_sha256": task_digest, "task": task,
    }
    decision = {
        "verdict": "request_changes", "summary": "finding",
        "findings": [{"path": "src/a.py", "start_line": 1, "end_line": 1, "content": "bug"}],
        "reviewed_head_sha": evidence["head_sha"],
        "task_identity_sha256": task_digest,
        "review_result_sha256": "e" * 64,
        "task": task,
    }
    return cfg, evidence, decision


def test_artifact_redacts_secret_shaped_findings_and_rehydrates_canonical_task(tmp_path: Path):
    cfg, evidence, decision = _inputs(tmp_path)
    task_secret = "github_pat_" + "x" * 30
    finding_secret = "sk-" + "y" * 32
    evidence["task"] = {**evidence["task"], "body": f"Acceptance {task_secret}"}
    evidence["task_identity_sha256"] = hashlib.sha256(
        json.dumps(evidence["task"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["task"] = evidence["task"]
    decision["task_identity_sha256"] = evidence["task_identity_sha256"]
    decision["findings"] = [{
        "path": "src/a.py", "start_line": 1, "end_line": 1,
        "content": f"Hard-coded credential {finding_secret}",
        "existing_code": f"Authorization: Bearer {finding_secret}",
    }]
    cfg.pr_review_binary_sha256 = "f" * 64

    stored = persist_result(cfg=cfg, repo="acme/demo", pr=84, evidence=evidence, decision=decision)
    assert stored["ok"] is True
    raw = Path(stored["path"]).read_text(encoding="utf-8")
    assert task_secret not in raw
    assert finding_secret not in raw
    assert "[redacted]" in raw
    assert "Acceptance" not in raw
    loaded = load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"], evidence=evidence,
    )
    assert loaded["decision"]["task"] == evidence["task"]


def test_artifact_restore_requires_canonical_task_evidence(tmp_path: Path):
    cfg, evidence, decision = _inputs(tmp_path)
    stored = persist_result(cfg=cfg, repo="acme/demo", pr=84, evidence=evidence, decision=decision)
    assert stored["ok"] is True

    assert load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"],
    ) is None


def test_artifact_cache_restores_complete_structured_review_identity(tmp_path: Path):
    cfg, evidence, decision = _inputs(tmp_path)
    decision.update(
        review_input_fingerprint_sha256="1" * 64,
        review_preview_sha256="2" * 64,
        review_rule_config_sha256="3" * 64,
        review_runtime_config_sha256="4" * 64,
    )
    stored = persist_result(
        cfg=cfg, repo="acme/demo", pr=84, evidence=evidence, decision=decision
    )
    assert stored["ok"] is True
    loaded = load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"], evidence=evidence,
    )
    assert loaded is not None
    assert loaded["decision"]["review_result_sha256"] == "e" * 64
    assert loaded["decision"]["reviewed_head_sha"] == "b" * 40
    assert loaded["decision"]["task_identity_sha256"] == evidence["task_identity_sha256"]
    assert loaded["decision"]["review_input_fingerprint_sha256"] == "1" * 64
    assert loaded["decision"]["review_preview_sha256"] == "2" * 64
    assert loaded["decision"]["review_rule_config_sha256"] == "3" * 64
    assert loaded["decision"]["review_runtime_config_sha256"] == "4" * 64


def test_artifact_restores_findings_only_when_digest_and_live_identity_match(tmp_path: Path):
    cfg, evidence, decision = _inputs(tmp_path)
    stored = persist_result(cfg=cfg, repo="acme/demo", pr=84, evidence=evidence, decision=decision)
    assert stored["ok"] is True

    loaded = load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"], evidence=evidence,
    )
    assert loaded["decision"]["findings"] == decision["findings"]
    assert loaded["decision"]["task"] == evidence["task"]

    changed = {**evidence, "diff_sha256": "0" * 64}
    assert load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"], evidence=changed,
    ) is None

    Path(stored["path"]).write_text("{}", encoding="utf-8")
    assert load_verified_result(
        cfg=cfg, repo="acme/demo", pr=84, head_sha="b" * 40,
        artifact_sha256=stored["artifact_sha256"], evidence=evidence,
    ) is None
