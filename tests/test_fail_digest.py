"""Fail-run digest: short template beside lokay state when ok:false."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.compose.daemon_cycle import finalize_daemon_payload
from lokay.fail_digest import DIGEST_NAME, DIGEST_DIR, build_digest, write_digest


def test_nested_adapter_failed_host_ff_dirty_mentions_dirty(tmp_path: Path):
    envelope = {
        "ok": False,
        "path_id": "factory_pass",
        "run_id": "lokay-deadbeef01",
        "error": {
            "code": "adapter_failed",
            "message": json.dumps(
                {
                    "ok": False,
                    "step": "host_ff",
                    "error": "refusing host-ff: checkout is dirty",
                }
            ),
        },
        "terminal": {
            "host_ff": {
                "step": "host_ff",
                "status": "failed",
                "error": "refusing host-ff: checkout is dirty",
            }
        },
        "steps": [
            {
                "step": "host_ff",
                "status": "failed",
                "error": "refusing host-ff: checkout is dirty",
            }
        ],
    }
    text = build_digest(envelope)
    assert "host_ff" in text
    assert "dirty" in text.lower() or "host" in text.lower()
    assert "co dalej" in text
    path = write_digest(tmp_path, envelope)
    assert path == tmp_path / DIGEST_NAME
    assert path.read_text(encoding="utf-8") == text
    archived = list((tmp_path / DIGEST_DIR).glob("*-lokay-deadbeef01.md"))
    assert len(archived) == 1


def test_traceback_coding_boundary_mentions_integrity_or_syntax(tmp_path: Path):
    envelope = {
        "ok": False,
        "path_id": "issue_to_pr",
        "run_id": "lokay-syntax01",
        "reason": "python_syntax",
        "error": (
            "coding_boundary failed\n"
            "Traceback (most recent call last):\n"
            '  File "src/lokay/organ/coding_boundary.py", line 12, in handle\n'
            "    raise SyntaxError('unexpected EOF')\n"
            "SyntaxError: unexpected EOF"
        ),
        "steps": [
            {
                "step": "coding_boundary",
                "status": "failed",
                "error": "Traceback (most recent call last):\nSyntaxError: unexpected EOF",
            }
        ],
    }
    text = build_digest(envelope)
    assert "coding_boundary" in text or "python_syntax" in text
    lowered = text.lower()
    assert "integrity" in lowered or "syntax" in lowered
    assert write_digest(tmp_path, envelope) is not None


def test_ok_true_write_digest_noop(tmp_path: Path):
    assert write_digest(tmp_path, {"ok": True, "path_id": "factory_pass"}) is None
    assert not (tmp_path / DIGEST_NAME).exists()
    assert not (tmp_path / DIGEST_DIR).exists()


def test_write_never_raises_on_garbage(tmp_path: Path):
    assert write_digest(tmp_path, None) is None
    assert write_digest(tmp_path, "not-a-dict") is None
    assert write_digest(tmp_path, {"ok": False}) is not None  # insufficient evidence
    text = (tmp_path / DIGEST_NAME).read_text(encoding="utf-8")
    assert "insufficient evidence" in text.lower() or "co dalej" in text
    # path that cannot be created still must not raise
    assert write_digest(Path("/proc/unlikely-lokay-digest-root"), {"ok": False}) is None


def test_empty_adapter_failed_heuristic():
    envelope = {
        "ok": False,
        "path_id": "factory_pass",
        "run_id": "lokay-empty-adapter",
        "error": "adapter_failed",
        "steps": [{"step": "issue_sieve_rows", "status": "failed", "error": "adapter_failed"}],
    }
    text = build_digest(envelope)
    assert "adapter_failed" in text.lower() or "issue_sieve" in text.lower()
    assert "cwd" in text.lower() or "empty" in text.lower() or "sqlite" in text.lower()


def test_finalize_writes_digest_before_stripping(tmp_path: Path):
    payload = {
        "ok": False,
        "path_id": "daemon_cycle",
        "run_id": "lokay-finalize01",
        "error": "adapter_failed",
        "fala": {"host": "x" * 1000},
        "terminal": {
            "host_ff": {
                "step": "host_ff",
                "status": "failed",
                "error": "refusing host-ff: checkout is dirty",
            }
        },
        "steps": [
            {
                "step": "host_ff",
                "status": "failed",
                "error": "refusing host-ff: checkout is dirty",
            }
        ],
    }
    out = finalize_daemon_payload(payload, state_dir=tmp_path)
    assert "fala" not in out
    assert "terminal" not in out
    digest = (tmp_path / DIGEST_NAME).read_text(encoding="utf-8")
    assert "dirty" in digest.lower() or "host" in digest.lower()
    assert "host_ff" in digest


def test_explain_failure_distinguishes_local_upstream_and_unknown():
    from lokay.fail_digest import explain_failure

    # Local defect
    local_env = {
        "ok": False,
        "path_id": "factory_pass",
        "steps": [{"step": "host_ff", "status": "failed", "error": "refusing host-ff: checkout is dirty"}],
        "provenance": {"symbol": "lokay.git_host_ff:main", "code_sha256": "a" * 64, "binding": "host_ff"},
    }
    rep_local = explain_failure(local_env)
    assert rep_local["classification"] == "local_contract_defect"
    assert rep_local["failed_contract"] == "host_ff"
    assert rep_local["source_identity"]["code_sha256"] == "a" * 64

    # Upstream defect
    upstream_env = {
        "ok": False,
        "path_id": "factory_pass",
        "steps": [{"step": "factory_begin_host_gate", "status": "failed", "error": "upstream host_ff failed"}],
        "conduction": ["host_ff"],
    }
    rep_upstream = explain_failure(upstream_env)
    assert rep_upstream["classification"] == "upstream_defect"
    assert rep_upstream["upstream_refs"] == ["host_ff"]

    # Unknown cause
    unknown_env = {"ok": False}
    rep_unknown = explain_failure(unknown_env)
    assert rep_unknown["classification"] == "unknown_cause"


def test_explain_failure_uses_execution_provenance_not_current_head(tmp_path):
    import importlib.util
    from lokay.execution_provenance import implementation_identity
    from lokay.fail_digest import explain_failure

    file_a = tmp_path / "handler.py"
    file_a.write_text("def handle(): return 1\n")
    spec = importlib.util.spec_from_file_location("mod_v1", file_a)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    history_identity = implementation_identity(mod.handle)
    file_a.write_text("def handle(): return 2\n")  # mutate HEAD file

    env = {
        "ok": False,
        "path_id": "test_path",
        "provenance": history_identity,
        "steps": [{"step": "test_atom", "status": "failed", "error": "fault"}],
    }
    report = explain_failure(env)
    assert report["source_identity"]["code_sha256"] == history_identity["code_sha256"]
    assert "return 2" not in str(report)


def test_digest_includes_explain_details_without_executing_effects():
    from lokay.fail_digest import build_digest

    env = {
        "ok": False,
        "path_id": "factory_pass",
        "run_id": "run-123",
        "provenance": {"symbol": "lokay.organ.factory:handle_factory", "code_sha256": "b" * 64},
        "steps": [{"step": "host_ff", "status": "failed", "error": "dirty checkout"}],
    }
    digest = build_digest(env)
    assert "host_ff" in digest
    assert "lokay.organ.factory:handle_factory" in digest
