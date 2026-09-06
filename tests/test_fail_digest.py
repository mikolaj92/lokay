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
