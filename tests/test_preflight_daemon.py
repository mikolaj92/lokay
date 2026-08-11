import os
import subprocess
from pathlib import Path


def test_daemon_bootstraps_before_uv_and_has_no_product_bypass():
    script = (Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh").read_text()
    daemon_command = 'uv run --reinstall-package lokay --reinstall-package fala lokay-daemon'
    assert script.index('command -v uv') < script.index(daemon_command)
    assert script.count(daemon_command) == 1
    assert 'uv run lokay-repos' not in script
    assert 'uv run lokay-mill' not in script
    assert 'preflight-bootstrap-incidents.log' in script


def test_daemon_handles_missing_home_and_bounds_bootstrap_outbox():
    script = (Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh").read_text()
    assert 'HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"' in script
    assert 'wc -c < "${OUTBOX}"' in script
    assert '-ge 65536' in script
    assert ': > "${OUTBOX}"' in script


def test_daemon_exposes_local_pi_to_preflight(tmp_path):
    """Issue #15: exercise the shell boundary used by launchd, not only the
    Python PATH repair helper."""
    root = tmp_path / "repo"
    local_bin = tmp_path / ".local" / "bin"
    root.mkdir()
    local_bin.mkdir(parents=True)
    (root / "config.yaml").touch()
    (local_bin / "pi").write_text("#!/bin/sh\nexit 0\n")
    (local_bin / "pi").chmod(0o755)
    (local_bin / "uv").write_text(
        "#!/bin/sh\n"
        "test \"$1 $2 $3 $4 $5\" = 'run --reinstall-package lokay --reinstall-package fala' || exit 64\n"
        "printf '%s\\n' \"$(command -v pi)\" \"$PATH\"\n"
    )
    (local_bin / "uv").chmod(0o755)

    completed = subprocess.run(
        ["/bin/bash", str(Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh")],
        env={
            "HOME": str(tmp_path),
            "LOKAY_ROOT": str(root),
            "LOKAY_CONFIG": str(root / "config.yaml"),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == str(local_bin / "pi")
    assert lines[1].split(os.pathsep)[0] == str(local_bin)
