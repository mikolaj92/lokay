"""HTMX / hypermedia boundaries (issue #15).

Lokay is CLI-first. When HTML appears, server owns state: fragments not SPA.
These guards fail closed on hidden SPA patterns and non-progressive forms.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# Product tree only — tests may mention forbidden stacks as negative examples.
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

# Product SPA / client-render stacks (ban for core chrome / domain UI).
SPA_MARKERS = re.compile(
    r"""(?ix)
    \bfrom\s+['"]react['"]
    |\brequire\s*\(\s*['"]react['"]
    |\bfrom\s+['"]react-dom
    |\bcreateRoot\s*\(
    |\bReactDOM\b
    |\bfrom\s+['"]vue['"]
    |\bcreateApp\s*\(
    |\bfrom\s+['"]@angular/
    |\bfrom\s+['"]svelte
    |\bfrom\s+['"]solid-js
    |\bfrom\s+['"]preact
    |\bnext/router\b
    |\b__NEXT_DATA__\b
    """
)

# JSON fetched then rendered client-side into chrome / primary UI.
JSON_CLIENT_RENDER = re.compile(
    r"""(?ix)
    (?:
      innerHTML\s*=
      |insertAdjacentHTML\s*\(
      |document\.write\s*\(
    )
    .{0,200}
    (?:
      \.json\s*\(
      |JSON\.parse
      |response\.json
    )
    |
    (?:
      \.json\s*\(
      |JSON\.parse
      |response\.json
    )
    .{0,200}
    (?:
      innerHTML\s*=
      |insertAdjacentHTML\s*\(
      |document\.write\s*\(
    )
    """
)

# hx-target must prefer stable #id (not closest/find/querySelector chains).
HX_TARGET_ATTR = re.compile(
    r"""(?ix)hx-target\s*=\s*["']([^"']+)["']"""
)

# Forms: if present, need action+method for progressive enhancement
# (hx-* alone is not enough).
FORM_TAG = re.compile(r"(?is)<form\b([^>]*)>")


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


def test_htmx_binding_doc_exists():
    doc = ROOT / "docs" / "HTMX.md"
    assert doc.is_file(), "docs/HTMX.md is binding — do not delete"
    text = doc.read_text(encoding="utf-8")
    for needle in (
        "Server owns state",
        "HTML fragments",
        "Progressive enhancement",
        "No client template SPA",
    ):
        assert needle in text, f"docs/HTMX.md missing rule text: {needle}"


def test_no_spa_framework_markers_in_product_code():
    hits: list[str] = []
    for path in _iter_files(CODE_GLOBS + HTML_GLOBS):
        text = _read(path)
        if SPA_MARKERS.search(text):
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: SPA / client-framework marker")
    assert not hits, (
        "Hidden SPA patterns forbidden (prefer server HTML + HTMX):\n"
        + "\n".join(hits)
    )


def test_no_json_plus_client_render_for_chrome():
    hits: list[str] = []
    for path in _iter_files(CODE_GLOBS + HTML_GLOBS):
        text = _read(path)
        if JSON_CLIENT_RENDER.search(text):
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: JSON + client HTML injection")
    assert not hits, (
        "No JSON+client-render for core chrome / UI "
        "(return HTML fragments from the server):\n" + "\n".join(hits)
    )


def test_html_forms_progressive_when_present():
    """Forms must keep action+method so they work without JS."""
    html_files = _iter_files(HTML_GLOBS)
    # CLI-only tree: zero HTML is compliant.
    if not html_files:
        return

    bad: list[str] = []
    for path in html_files:
        text = _read(path)
        for m in FORM_TAG.finditer(text):
            attrs = m.group(1)
            has_action = re.search(r"(?i)\baction\s*=", attrs) is not None
            has_method = re.search(r"(?i)\bmethod\s*=", attrs) is not None
            if not (has_action and has_method):
                rel = path.relative_to(ROOT)
                bad.append(f"{rel}: <form> missing action and/or method")
    assert not bad, (
        "Progressive enhancement: forms need action+method "
        "(HTMX is additive):\n" + "\n".join(bad)
    )


def test_hx_target_uses_stable_ids_when_present():
    html_files = _iter_files(HTML_GLOBS)
    if not html_files:
        return

    bad: list[str] = []
    for path in html_files:
        text = _read(path)
        for m in HX_TARGET_ATTR.finditer(text):
            target = m.group(1).strip()
            # this, closest, find, next, previous — brittle relative selectors
            if target.startswith("#"):
                continue
            if target in {"this", "body", "html"}:
                continue
            # Allow CSS id-less but simple class? Prefer ban non-id for stability.
            if target.startswith(".") or " " in target or target.startswith("closest"):
                rel = path.relative_to(ROOT)
                bad.append(f"{rel}: hx-target={target!r} — prefer #id")
            elif target.startswith("find") or target.startswith("next") or target.startswith(
                "previous"
            ):
                rel = path.relative_to(ROOT)
                bad.append(f"{rel}: hx-target={target!r} — prefer #id")
    assert not bad, "Stable hx-target ids required:\n" + "\n".join(bad)


def test_cli_envelope_is_not_browser_chrome_api():
    """JSON on stdout is process I/O, not a UI data plane."""
    env = SRC / "lokay" / "envelope.py"
    assert env.is_file()
    text = env.read_text(encoding="utf-8")
    # Must remain a small CLI helper — not grow browser template rendering.
    assert "innerHTML" not in text
    assert "hx-" not in text
