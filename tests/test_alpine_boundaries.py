"""Alpine boundaries (issue #16).

Lokay is CLI-first. When Alpine appears, it may only hold local UI state
(toggles/menus/disclosure). No app-wide store of server data; menus/dialogs
must stay keyboard accessible.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# Product tree only — tests may mention forbidden patterns as negative examples.
SCAN_ROOTS = (SRC, ROOT / "scripts")
HTML_GLOBS = ("**/*.html", "**/*.htm", "**/*.jinja", "**/*.j2", "**/*.jinja2")
CODE_GLOBS = (
    "**/*.py",
    "**/*.js",
    "**/*.mjs",
    "**/*.cjs",
    "**/*.ts",
    "**/*.tsx",
    "**/*.jsx",
)

# App-wide Alpine store (forbidden unless already present — it is not).
ALPINE_STORE = re.compile(
    r"""(?ix)
    \bAlpine\s*\.\s*store\s*\(
    |\$store\s*\.
    """
)

# Alpine directive / API presence in markup or script.
ALPINE_MARK = re.compile(
    r"""(?ix)
    \bx-data\b
    |\bx-show\b
    |\bx-if\b
    |\bx-model\b
    |\bx-on:
    |\b@click\b
    |\bAlpine\s*\.
    |\balpinejs\b
    |\balpine\.js\b
    """
)

# Rough menu / dialog shells that Alpine often drives.
MENU_OR_DIALOG = re.compile(
    r"""(?ix)
    \brole\s*=\s*["'](?:dialog|menu|listbox|menu(?:bar)?|combobox)["']
    |<\s*dialog\b
    |\baria-haspopup\b
    |\baria-expanded\b
    """
)

# Escape key handling (keyboard close path).
ESCAPE_HANDLER = re.compile(
    r"""(?ix)
    @keydown\.escape
    |@keyup\.escape
    |x-on:keydown\.escape
    |x-on:keyup\.escape
    |keydown\.escape
    |key\s*===\s*['"]Escape['"]
    |key\s*==\s*['"]Escape['"]
    |code\s*===\s*['"]Escape['"]
    |\.escape\b
    """
)


def _iter_files(globs: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for pattern in globs:
            out.extend(p for p in root.glob(pattern) if p.is_file())
    return sorted(set(out))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def test_alpine_binding_doc_exists():
    doc = ROOT / "docs" / "ALPINE.md"
    assert doc.is_file(), "docs/ALPINE.md is binding — do not delete"
    text = doc.read_text(encoding="utf-8")
    for needle in (
        "Local UI state only",
        "No app-wide Alpine store",
        "No server-state mirrors",
        "keyboard accessible",
    ):
        assert needle in text, f"docs/ALPINE.md missing rule text: {needle}"


def test_no_alpine_global_store_in_product_code():
    """Ban Alpine.store / $store — none exists today; do not introduce one."""
    hits: list[str] = []
    for path in _iter_files(CODE_GLOBS + HTML_GLOBS):
        text = _read(path)
        if ALPINE_STORE.search(text):
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: Alpine global store")
    assert not hits, (
        "No app-wide Alpine store for server/domain data "
        "(local x-data only; see docs/ALPINE.md):\n" + "\n".join(hits)
    )


def test_alpine_menus_dialogs_have_escape_when_present():
    """Alpine-driven menus/dialogs need an Escape close path."""
    html_files = _iter_files(HTML_GLOBS)
    # CLI-only tree: zero HTML is compliant.
    if not html_files:
        return

    bad: list[str] = []
    for path in html_files:
        text = _read(path)
        if not ALPINE_MARK.search(text):
            continue
        if not MENU_OR_DIALOG.search(text):
            continue
        if not ESCAPE_HANDLER.search(text):
            rel = path.relative_to(ROOT)
            bad.append(
                f"{rel}: Alpine menu/dialog missing Escape keyboard close"
            )
    assert not bad, (
        "Menus/dialogs driven by Alpine must be keyboard accessible "
        "(at least Escape to close):\n" + "\n".join(bad)
    )


def test_alpine_menus_dialogs_use_accessible_controls_when_present():
    """Prefer real buttons / native dialog / ARIA over inert div click targets."""
    html_files = _iter_files(HTML_GLOBS)
    if not html_files:
        return

    # A click-only div toggle for a menu/dialog is a common a11y failure.
    inert_toggle = re.compile(
        r"""(?is)
        <div\b[^>]*(?:@click|x-on:click)[^>]*>
        """
    )
    has_button_or_dialog = re.compile(
        r"""(?ix)
        <\s*button\b
        |<\s*dialog\b
        |\brole\s*=\s*["'](?:button|dialog|menu)["']
        """
    )

    bad: list[str] = []
    for path in html_files:
        text = _read(path)
        if not ALPINE_MARK.search(text):
            continue
        if not MENU_OR_DIALOG.search(text):
            continue
        if inert_toggle.search(text) and not has_button_or_dialog.search(text):
            rel = path.relative_to(ROOT)
            bad.append(
                f"{rel}: Alpine menu/dialog uses div@click without button/dialog"
            )
    assert not bad, (
        "Menus/dialogs need keyboard-focusable controls "
        "(button / dialog / role):\n" + "\n".join(bad)
    )


def test_cli_envelope_is_not_alpine_data_plane():
    """JSON envelopes stay process I/O — not Alpine domain state."""
    env = SRC / "lokay" / "envelope.py"
    assert env.is_file()
    text = env.read_text(encoding="utf-8")
    assert "x-data" not in text
    assert "Alpine" not in text
    assert "$store" not in text
