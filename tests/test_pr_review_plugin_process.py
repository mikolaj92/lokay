from __future__ import annotations

import json
import os
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


@pytest.mark.parametrize("failure", ["cancel", "timeout", "output"])
def test_review_failure_stops_ocr_descendants(tmp_path, monkeypatch, failure):
    import signal
    import sys
    import time
    from pathlib import Path

    monkeypatch.setenv("OCR_PROVIDER_KEY", "test-key")
    pidfile = tmp_path / "ocr.pid"
    plugin_src = Path(__file__).resolve().parents[1] / "plugins/pr_review_open_code_review/src"
    descendant = (
        "import os,time; from pathlib import Path; "
        f"Path({str(pidfile)!r}).write_text(f'{{os.getpid()}} {{os.getpgrp()}}'); time.sleep(30)"
    )
    ocr = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}]); "
        f"p=Path({str(pidfile)!r}); "
        "exec('while not p.exists(): time.sleep(0.01)'); "
        + ("sys.stdout.write('x'*100000); sys.stdout.flush(); " if failure == "output" else "")
        + "time.sleep(30)"
    )
    plugin = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(plugin_src)!r}); "
        "from lokay_review_open_code_review.cli import _run_bounded; "
        f"_run_bounded([sys.executable, '-c', {ocr!r}], "
        f"cwd=Path({str(tmp_path)!r}), env={{'PATH':'/usr/bin:/bin'}}, "
        f"timeout_seconds={0.2 if failure == 'timeout' else 30}, max_bytes=32)"
    )
    owner_code = (
        "from types import SimpleNamespace; "
        "from lokay.proc.pr_review_plugin import invoke_plugin; "
        f"invoke_plugin(SimpleNamespace(pr_review_plugin_command={sys.executable!r}, "
        f"pr_review_plugin_args=['-c', {plugin!r}], pr_review_plugin_timeout_seconds=30, "
        "pr_review_provider_env=['OCR_PROVIDER_KEY']), {})"
    )
    owner = subprocess.Popen(
        [sys.executable, "-c", owner_code], start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    ocr_pid = 0
    plugin_pgid = 0
    try:
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pidfile.exists(), "OCR did not start"
        ocr_pid, plugin_pgid = map(int, pidfile.read_text().split())
        if failure == "cancel":
            os.killpg(owner.pid, signal.SIGTERM)
        assert owner.wait(timeout=3) != 0
        stat = "running"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            stat = subprocess.run(
                ["ps", "-p", str(ocr_pid), "-o", "stat="], capture_output=True, text=True,
            ).stdout.strip()
            if not stat or stat.startswith("Z"):
                break
            time.sleep(0.02)
        assert not stat or stat.startswith("Z"), "failed review left OCR descendants running"
    finally:
        for pgid in (owner.pid, plugin_pgid):
            if pgid:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
        if ocr_pid:
            try:
                os.kill(ocr_pid, signal.SIGKILL)
            except OSError:
                pass
        owner.wait(timeout=3)


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
        (b'{}\n{}', 0, "ocr_output_not_json"),
        (b'{"ok":false}', 1, "ocr_exited_unsuccessfully"),
        (b'provider-secret', 0, "ocr_output_not_json"),
        (b'{"ok":true}', 7, "ocr_exited_unsuccessfully"),
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
    with pytest.raises(PluginFailure, match="ocr_output_too_large"):
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


def test_absolute_plugin_can_run_git_without_inheriting_host_path(monkeypatch, tmp_path):
    import sys

    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("PATH", str(tmp_path / "untrusted-host-bin"))
    plugin = tmp_path / "review-plugin"
    plugin.write_text(
        f"#!{sys.executable}\n"
        "import json, os, subprocess\n"
        "git = subprocess.run(['git', '--version'], capture_output=True, check=True)\n"
        "print(json.dumps({'ok': True, 'git': git.stdout.decode(), 'path': os.environ['PATH']}))\n"
    )
    plugin.chmod(0o700)

    result = invoke_plugin(_config(pr_review_plugin_command=str(plugin)), {})

    assert result["git"].startswith("git version ")
    assert str(tmp_path / "untrusted-host-bin") not in result["path"].split(os.pathsep)


def test_process_boundary_resolves_pi_credential_at_plugin_boundary(monkeypatch):
    monkeypatch.delenv("OCR_LLM_API_KEY", raising=False)
    monkeypatch.setattr(
        "lokay.proc.pr_review_plugin.resolve_pi_api_key",
        lambda: "resolved-review-credential",
    )
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(
            argv, 0, stdout=b'{"ok":true,"schema":"lokay.review-result/1"}'
        )

    result = invoke_plugin(
        _config(pr_review_provider_env=["OCR_LLM_API_KEY"]),
        {"schema": "lokay.review-request/1"},
        runner=run,
    )

    assert result["ok"] is True
    assert seen["env"]["OCR_LLM_API_KEY"] == "resolved-review-credential"
    assert "OCR_LLM_API_KEY" not in os.environ


def test_process_boundary_rejects_bad_credential_names_before_start(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "github-secret")
    cfg = _config(pr_review_provider_env=["GH_TOKEN"])
    with pytest.raises(PluginFailure, match="allowlist"):
        invoke_plugin(cfg, {}, runner=lambda *_a, **_k: pytest.fail("must not run"))


def test_process_boundary_surfaces_classified_plugin_error_code(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("GH_TOKEN", "github-secret")

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout=b'{"ok":false,"error":{"code":"ocr_exited_unsuccessfully"}}',
            stderr=b"provider-secret github-secret",
        )

    with pytest.raises(PluginFailure, match="ocr_exited_unsuccessfully") as caught:
        invoke_plugin(_config(), {"request": True}, runner=run)
    assert "provider-secret" not in str(caught.value)
    assert "github-secret" not in str(caught.value)
    assert "failure status" not in str(caught.value)


def test_process_boundary_keeps_contract_rejection_detail(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("GH_TOKEN", "github-secret")

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout=(
                b'{"ok":false,"error":{"code":"ocr_contract_rejected",'
                b'"detail":"review terminal state is not complete"}}'
            ),
            stderr=b"provider-secret github-secret",
        )

    with pytest.raises(PluginFailure, match="ocr_contract_rejected") as caught:
        invoke_plugin(_config(), {"request": True}, runner=run)
    assert "review terminal state is not complete" in str(caught.value)
    assert "provider-secret" not in str(caught.value)
    assert "github-secret" not in str(caught.value)


def test_process_boundary_keeps_redacted_vendor_warnings(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_KEY", "provider-secret")
    monkeypatch.setenv("GH_TOKEN", "github-secret")

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout=(
                b'{"ok":false,"error":{"code":"ocr_contract_rejected",'
                b'"detail":"review has warnings",'
                b'"warnings":[{"type":"token_budget_reached","file":"src/demo.py"}]}}'
            ),
            stderr=b"provider-secret github-secret",
        )

    with pytest.raises(PluginFailure, match="ocr_contract_rejected") as caught:
        invoke_plugin(_config(), {"request": True}, runner=run)
    assert caught.value.warnings == [{"type": "token_budget_reached", "file": "src/demo.py"}]
    assert "provider-secret" not in str(caught.value)
    assert "github-secret" not in str(caught.value)
