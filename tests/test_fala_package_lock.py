"""Fail-closed lock: checkout Fala and packaged wheel copy must not drift."""

import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / "fala" / "lokay.fala-package.toml"
PACKAGED = ROOT / "src" / "lokay" / "data" / "lokay.fala-package.toml"
PINNED_FALA = "4a956c665c8e3cb9f10be9ffcb02e3b27b11c6bd"
PINNED_FALA_VERSION = "0.9.4"


def test_packaged_fala_is_byte_identical_to_checkout():
    """Wheel/install lokay must ship the same source graph as fala/.

    ``graph_run.find_default_package`` prefers checkout then packaged data.
    ``PLACEHOLDER_PROJECT`` is substituted at run time only — both files are
    the same unsubstituted source text.
    """
    authored = CHECKOUT.read_bytes()
    packaged = PACKAGED.read_bytes()
    assert authored == packaged, (
        "src/lokay/data/lokay.fala-package.toml drifted from "
        "fala/lokay.fala-package.toml; copy the checkout graph so a wheel lokay "
        "cannot run a stale Fala (missing gates)"
    )
    assert b"PLACEHOLDER_PROJECT" in authored


def test_correlation_path_titles_and_descriptions_are_ascii():
    """Fala toml.mojo slices descriptions by byte; mid-codepoint is exit 33."""
    text = CHECKOUT.read_text(encoding="utf-8")
    in_path = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[[correlation_paths]]":
            in_path = True
            continue
        if stripped.startswith("[[") and not stripped.startswith("[[correlation_paths"):
            in_path = False
        if not in_path:
            continue
        if stripped.startswith(("title =", "description =")):
            assert all(ord(ch) < 128 for ch in line), line


def test_python_fala_dependency_uses_immutable_git_tag():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    source = pyproject["tool"]["uv"]["sources"]["fala"]
    assert source == {
        "git": "https://github.com/mikolaj92/Fala.git",
        "rev": PINNED_FALA,
    }
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'editable = "../Fala"' not in lock
    assert f'version = "{PINNED_FALA_VERSION}"' in lock
    assert f"#{PINNED_FALA}" in lock


def _git_head(path: Path) -> str:
    run = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        pytest.fail(f"{path} is not a git checkout: {run.stderr.strip()}")
    return run.stdout.strip()


def test_sibling_fala_checkout_matches_pinned_revision():
    """graph_run falls back to ../Fala when FALA_HOME is unset.

    A stale 0.9.3 sibling mixes wheel 0.9.4 with native 0.9.3 and skips `when`.
    """
    sibling = ROOT.parent / "Fala"
    assert sibling.is_dir(), f"canonical Fala checkout missing at {sibling}"
    assert _git_head(sibling) == PINNED_FALA, (
        f"{sibling} HEAD is {_git_head(sibling)}; pin is {PINNED_FALA} "
        f"({PINNED_FALA_VERSION})"
    )
    pixi = tomllib.loads((sibling / "pixi.toml").read_text(encoding="utf-8"))
    assert pixi["workspace"]["version"] == PINNED_FALA_VERSION


def test_service_default_fala_home_is_the_canonical_checkout():
    script = (ROOT / "scripts" / "lokay-service.sh").read_text(encoding="utf-8")
    assert 'FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"' in script


def _plist_fala_home(path: Path) -> str | None:
    if not path.is_file():
        return None
    run = subprocess.run(
        ["/usr/bin/plutil", "-extract", "EnvironmentVariables.FALA_HOME", "raw", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        return None
    return run.stdout.strip() or None


def test_host_launchagents_use_canonical_fala_checkout():
    """A /tmp worktree is a pin scratchpad, not the host native home."""
    canonical = Path.home() / "Developer" / "OSS" / "Fala"
    agents = Path.home() / "Library" / "LaunchAgents"
    for name in ("ai.mikolaj.lokay.plist", "ai.mikolaj.lokay-status.plist"):
        home = _plist_fala_home(agents / name)
        if home is None:
            continue
        assert home == str(canonical), (
            f"{name} FALA_HOME={home!r}; expected canonical {canonical}"
        )
