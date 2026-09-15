from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from lokay.proc.pr_review_plugin import PluginFailure, invoke_plugin


def _config(**updates):
    values = {
        "pr_review_plugin_command": "review-plugin",
        "pr_review_plugin_args": ["--json"],
        "pr_review_plugin_timeout_seconds": 12,
        "pr_review_provider_env": ["OCR_PROVIDER_KEY"],
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_process_boundary_sends_one_request_with_minimal_environment(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("GH_TOKEN", "github-secret")
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "lease-secret")
    seen = {}

    def run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok":true,"schema":"lokay.review-result/1"}')

    result = invoke_plugin(_config(), {"schema": "lokay.review-request/1"}, runner=run)

    assert result["schema"] == "lokay.review-result/1"
    assert json.loads(seen["input"]) == {"schema": "lokay.review-request/1"}
    assert seen["argv"] == ["review-plugin", "--json"]
    assert seen["env"]["OCR_PROVIDER_KEY"] == "provider-secret"
    assert "GH_TOKEN" not in seen["env"]
    assert "LOKAY_HEALTH_LEASE" not in seen["env"]
    assert seen["timeout"] == 12


@pytest.mark.parametrize(
    ("stdout", "returncode", "message"),
    [
        (b'{}\n{}', 0, "one JSON"),
        (b'{"ok":false}', 1, "failure status"),
        (b'provider-secret', 0, "one JSON"),
        (b'{"ok":true}', 7, "failure status"),
    ],
)
def test_process_boundary_fails_closed_for_bad_plugin_output(monkeypatch, stdout, returncode, message):
    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("GH_TOKEN", "github-secret")

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=b"provider-secret github-secret")

    with pytest.raises(PluginFailure, match=message) as caught:
        invoke_plugin(_config(), {"request": True}, runner=run)
    assert "provider-secret" not in str(caught.value)
    assert "github-secret" not in str(caught.value)


def test_process_boundary_kills_child_when_streamed_output_exceeds_limit(monkeypatch):
    import sys
    import time

    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setattr("lokay.proc.pr_review_plugin._MAX_OUTPUT_BYTES", 32)
    cfg = _config(
        pr_review_plugin_command=sys.executable,
        pr_review_plugin_args=["-c", "import sys,time; sys.stdout.write('x'*10000000); sys.stdout.flush(); time.sleep(3)"],
    )
    started = time.monotonic()
    with pytest.raises(PluginFailure, match="size limit"):
        invoke_plugin(cfg, {"request": True})
    assert time.monotonic() - started < 2


def test_process_boundary_drains_output_while_streaming_large_request(monkeypatch):
    import sys

    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    cfg = _config(
        pr_review_plugin_command=sys.executable,
        pr_review_plugin_args=[
            "-c",
            "import os,signal,sys; signal.alarm(3); os.write(1, b' '*131072); "
            "sys.stdin.buffer.read(); os.write(1, b'{\\\"ok\\\":true}')",
        ],
        pr_review_plugin_timeout_seconds=8,
    )
    request = {"padding": "x" * 512_000}

    result = invoke_plugin(cfg, request)

    assert result == {"ok": True}


def test_process_boundary_rejects_bad_credential_names_before_start(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "github-secret")
    cfg = _config(pr_review_provider_env=["GH_TOKEN"])
    with pytest.raises(PluginFailure, match="allowlist"):
        invoke_plugin(cfg, {}, runner=lambda *_a, **_k: pytest.fail("must not run"))
