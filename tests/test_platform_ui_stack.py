"""Platform UI stack (issue #12).

Lokay is CLI-first with a local read-only status host. Its chrome uses
app-factory product_shell plus same-origin Basecoat/HTMX/Alpine assets.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# Product tree only — tests may mention forbidden hosts as negative examples.
SCAN_ROOTS = (SRC, ROOT / "scripts")
DOCS = ROOT / "docs"
HTML_GLOBS = ("**/*.html", "**/*.htm", "**/*.jinja", "**/*.j2", "**/*.jinja2")
CODE_GLOBS = (
    "**/*.py",
    "**/*.js",
    "**/*.mjs",
    "**/*.cjs",
    "**/*.ts",
    "**/*.tsx",
    "**/*.jsx",
    "**/*.css",
)

# CDN / third-party hosts forbidden for core chrome stack.
CDN_CORE_MARKERS = re.compile(
    r"""(?ix)
    cdn\.jsdelivr\.net
    |unpkg\.com
    |cdnjs\.cloudflare\.com
    |htmx\.org/(?:dist|js)
    |alpinejs\.dev
    |cdn\.jsdelivr\.net/npm/(?:htmx|alpine|basecoat)
    |fonts\.googleapis\.com
    |fonts\.gstatic\.com
    """
)

# Script/link tags that pull htmx/alpine/basecoat from a non-platform origin.
CORE_STACK_CDN_TAG = re.compile(
    r"""(?ix)
    <(?:script|link)\b[^>]*(?:src|href)\s*=\s*["']https?://[^"']*
    (?:
      htmx
      |alpine(?:js)?
      |basecoat
    )
    """
)

# Half-integration / host-vendored chrome forks.
HOST_STACK_FORK = re.compile(
    r"""(?ix)
    htmx_alpine\.js
    |/static/vendor/(?:htmx|alpine|basecoat)
    |vendor/(?:htmx|alpine|basecoat)
    """
)

# Current immutable upstream COMPAT row. Only app-factory is installed because
# the local status host has no identity routes.
COMPAT_BOM = {
    "app-factory": "v0.6.16",
    "my-auth": "v0.4.8",
    "my-usermanager": "v0.5.11",
}


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


def test_platform_ui_binding_doc_exists():
    doc = DOCS / "PLATFORM_UI.md"
    assert doc.is_file(), "docs/PLATFORM_UI.md is binding — do not delete"
    text = doc.read_text(encoding="utf-8")
    for needle in (
        "product_shell",
        "/static/platform",
        "Basecoat",
        "HTMX",
        "Alpine",
        "COMPAT",
        "v0.6.16",
        "v0.4.8",
        "v0.5.11",
        "Same-origin",
        "CDN",
    ):
        assert needle in text, f"docs/PLATFORM_UI.md missing rule text: {needle}"


def test_compat_bom_pins_documented():
    """Document the exact immutable COMPAT row used by the status host."""
    doc = (DOCS / "PLATFORM_UI.md").read_text(encoding="utf-8")
    for package, tag in COMPAT_BOM.items():
        assert package in doc, f"COMPAT pin package missing: {package}"
        assert tag in doc, f"COMPAT pin tag missing for {package}: {tag}"
    # Do not recommend floating main for production host auth packages.
    assert 'branch = "main"' not in doc or "Do not float" in doc or "not float" in doc.lower()


def test_status_host_pins_current_app_factory_tag():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    source = pyproject["tool"]["uv"]["sources"]["app-factory"]
    assert source == {
        "git": "https://github.com/mikolaj92/app-factory.git",
        "tag": COMPAT_BOM["app-factory"],
    }


def test_no_cdn_for_core_stack_in_product_code():
    """Ban CDN hosts for htmx/alpine/basecoat (and fonts used as platform icons)."""
    hits: list[str] = []
    for path in _iter_files(CODE_GLOBS + HTML_GLOBS):
        text = _read(path)
        if CDN_CORE_MARKERS.search(text) or CORE_STACK_CDN_TAG.search(text):
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: CDN / third-party core-stack asset")
        if HOST_STACK_FORK.search(text):
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: host-vendored core-stack fork")
    assert not hits, (
        "Core stack (Basecoat/HTMX/Alpine) must be same-origin "
        "`/static/platform/...` via app-factory — no CDN forks:\n"
        + "\n".join(hits)
    )


def test_cli_only_has_no_auth_html_surfaces():
    """Smoke N/A: no login/account/admin HTML means no chrome CDN surface."""
    html_files = _iter_files(HTML_GLOBS)
    # CLI lokay today: zero templates is the compliant baseline.
    if not html_files:
        return

    # If HTML appears, auth chrome must not use CDN and should prefer platform.
    bad: list[str] = []
    authish = re.compile(
        r"""(?ix)
        \b(?:login|logout|register|account|admin)\b
        |product_shell
        |platform_session
        |platform_auth
        """
    )
    for path in html_files:
        text = _read(path)
        if not authish.search(text):
            continue
        rel = path.relative_to(ROOT)
        if CDN_CORE_MARKERS.search(text) or CORE_STACK_CDN_TAG.search(text):
            bad.append(f"{rel}: auth/chrome HTML loads core stack from CDN")
        # Prefer product_shell / platform assets when chrome is present.
        has_shell = "product_shell" in text or 'id="main-content"' in text
        has_platform = "/static/platform/" in text or "platform_asset_url" in text
        if not (has_shell or has_platform):
            bad.append(
                f"{rel}: auth/chrome HTML without product_shell or "
                "/static/platform assets"
            )
    assert not bad, (
        "Auth/chrome HTML must use product_shell + same-origin platform assets:\n"
        + "\n".join(bad)
    )


def test_no_floating_main_auth_pins_if_declared():
    """If my-auth / my-usermanager / app-factory are declared, use tags not main."""
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    # The status host declares app-factory; all platform pins must stay immutable.
    floating = re.compile(
        r"""(?ix)
        (?:app-factory|my-auth|my-usermanager)\s*=\s*\{[^}]*
        branch\s*=\s*["']main["']
        """
    )
    assert floating.search(text) is None, (
        "Do not float app-factory / my-auth / my-usermanager on branch=main; "
        "pin COMPAT tags (see docs/PLATFORM_UI.md)"
    )


def test_cli_envelope_is_not_platform_chrome():
    """JSON envelopes stay process I/O — not a browser chrome data plane."""
    env = SRC / "lokay" / "envelope.py"
    assert env.is_file()
    text = env.read_text(encoding="utf-8")
    assert "product_shell" not in text
    assert "/static/platform" not in text
    assert "cdn.jsdelivr" not in text
