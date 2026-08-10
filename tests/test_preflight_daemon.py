from pathlib import Path


def test_daemon_bootstraps_before_uv_and_has_no_product_bypass():
    script = (Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh").read_text()
    assert script.index('command -v uv') < script.index('uv run lokay-daemon')
    assert 'uv run lokay-repos' not in script
    assert 'uv run lokay-mill' not in script
    assert 'preflight-bootstrap-incidents.log' in script


def test_daemon_handles_missing_home_and_bounds_bootstrap_outbox():
    script = (Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh").read_text()
    assert 'HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"' in script
    assert 'wc -c < "${OUTBOX}"' in script
    assert '-ge 65536' in script
    assert ': > "${OUTBOX}"' in script
