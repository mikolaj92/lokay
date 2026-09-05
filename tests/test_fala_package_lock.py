"""Fail-closed lock: checkout Fala and packaged wheel copy must not drift."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / "fala" / "lokay.fala-package.toml"
PACKAGED = ROOT / "src" / "lokay" / "data" / "lokay.fala-package.toml"


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
        "tag": "v0.7.36",
    }
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'editable = "../Fala"' not in lock
