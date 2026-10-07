"""LaunchAgent lifecycle policy written by scripts/lokay-service.sh --install."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lokay-service.sh"


def _needs_plutil() -> None:
    if shutil.which("plutil") is None or not SCRIPT.is_file():
        pytest.skip("plutil or lokay-service.sh unavailable")


def _base_plist(tmp_path: Path) -> Path:
    """The observed 2026-09-28 plist: minute tick plus crash KeepAlive."""
    plist = tmp_path / "ai.mikolaj.lokay.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "Label": "ai.mikolaj.lokay",
                "ProgramArguments": ["/bin/bash", str(SCRIPT)],
                "StartInterval": 60,
                "KeepAlive": {"SuccessfulExit": False},
                "EnvironmentVariables": {"LOKAY_MAX_PASSES": "1"},
            }
        )
    )
    return plist


def _install(tmp_path: Path, plist: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["LOKAY_LAUNCHD_PLIST"] = str(plist)
    return subprocess.run(
        ["bash", str(SCRIPT), "--install"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_install_policy_is_run_at_load_and_crash_keepalive_only(tmp_path):
    _needs_plutil()
    plist = _base_plist(tmp_path)

    run = _install(tmp_path, plist)

    assert run.returncode == 0
    data = plistlib.loads(plist.read_bytes())
    assert "StartInterval" not in data  # no minute-based churn
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] == {"SuccessfulExit": False}


def test_install_keeps_missing_plist_missing(tmp_path):
    _needs_plutil()
    plist = tmp_path / "absent.plist"

    run = _install(tmp_path, plist)

    assert run.returncode == 0
    assert not plist.exists()  # do not invent a job


def test_tick_path_passes_resident_interval_to_daemon():
    """One lifecycle policy: the caretaker launches one resident daemon."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--interval" in text
    assert "LOKAY_DAEMON_INTERVAL" in text
    # The interval is only ever removed by host setup, never written back.
    assert "plutil -replace StartInterval" not in text
    assert "plutil -insert StartInterval" not in text
