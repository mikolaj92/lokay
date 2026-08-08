"""Host shell chrome placement (issue #13).

Lokay is CLI-first. When host HTML base/layout appears it must extend
app-factory product_shell: logout only via platform_session, theme/locale
only via platform partials, no host-copied shell/theme boot forks.
CLI-only (zero HTML under src/scripts) is compliant.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
# Product tree only — tests may mention forbidden chrome as negative examples.
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
)

# Filenames that must not be host-copied from platform chrome.
BANNED_CHROME_FILENAMES = frozenset(
    {
        "shell_boot.html",
        "theme_boot.html",
        "platform_foot.html",
        "product_shell.html",
    }
)

# Base/layout shell template names (when present must extend product_shell).
BASE_LAYOUT_NAME = re.compile(
    r"""(?ix)
    (?:^|[/\\])
    (?:
      base
      |layout
      |shell
      |app_shell
      |host_shell
      |main_layout
      |base_layout
    )
    \.(?:html|htm|jinja|j2|jinja2)$
    """
)

# Jinja extends product_shell (path variants).
EXTENDS_PRODUCT_SHELL = re.compile(
    r"""(?ix)
    \{\%\s*extends\s+
    ["'][^"']*product_shell[^"']*["']
    \s*\%\}
    """
)

# Logout control in markup (form action, link href, or visible label).
LOGOUT_MARK = re.compile(
    r"""(?ix)
    (?:
      action\s*=\s*["'][^"']*logout[^"']*["']
      |href\s*=\s*["'][^"']*logout[^"']*["']
      |>\s*log\s*out\s*<
      |>\s*sign\s*out\s*<
      |\blogout\b
      |\bsign[_-]?out\b
    )
    """
)

# platform_session include / partial reference.
PLATFORM_SESSION_INCLUDE = re.compile(
    r"""(?ix)
    platform_session
    |\{\%\s*(?:include|import|from)\s+["'][^"']*platform_session
    """
)

# Host-side theme boot forks (data-theme scripts, local toggles outside platform).
HOST_THEME_BOOT_FORK = re.compile(
    r"""(?ix)
    localStorage\s*\.\s*(?:get|set)Item\s*\(\s*["']theme["']
    |document\.documentElement\s*\.\s*(?:setAttribute|dataset)
      .{0,80}theme
    |data-theme\s*=
    |prefers-color-scheme
    |classList\s*\.\s*(?:add|toggle|remove)\s*\(\s*["']dark["']
    """
)

# Reimplementation of platform theme/locale chrome (host partial names).
HOST_THEME_LOCALE_REIMPL = re.compile(
    r"""(?ix)
    (?:^|[/\\])
    (?:
      theme_toggle
      |locale_switcher
      |theme_locale
      |host_theme
      |host_locale
    )
    \.(?:html|htm|jinja|j2|jinja2|js|mjs|cjs|ts)$
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


def _html_files() -> list[Path]:
    return _iter_files(HTML_GLOBS)


def test_chrome_placement_binding_doc():
    """PLATFORM_UI.md still documents chrome placement + issue #13 ACs."""
    doc = DOCS / "PLATFORM_UI.md"
    assert doc.is_file(), "docs/PLATFORM_UI.md is binding — do not delete"
    text = doc.read_text(encoding="utf-8")
    for needle in (
        "product_shell",
        "platform_session",
        "platform_theme_locale",
        "platform_auth",
        "platform_controls",
        "chrome placement",
        "Log out",
        "extends",
        "shell_boot",
        "theme_boot",
        "platform_foot",
        "#13",
    ):
        assert needle in text, f"docs/PLATFORM_UI.md missing chrome rule: {needle}"


def test_cli_only_zero_html_is_compliant():
    """Smoke N/A: no host HTML means no chrome fork surface (CLI mill)."""
    html_files = _html_files()
    # CLI mill today: zero templates is the compliant baseline.
    if not html_files:
        return
    # If HTML appears later, remaining tests in this module enforce placement.


def test_base_layout_extends_product_shell():
    """When base/layout shells appear, they must {% extends %} product_shell."""
    html_files = _html_files()
    if not html_files:
        return

    bad: list[str] = []
    for path in html_files:
        rel = path.relative_to(ROOT)
        name_match = BASE_LAYOUT_NAME.search(str(rel).replace("\\", "/"))
        text = _read(path)
        # Also treat files that look like app shells by content markers.
        content_shell = bool(
            re.search(
                r"""(?ix)
                \b(?:sidebar|main-header|app-shell|site-header)\b
                |id\s*=\s*["']main-content["']
                """,
                text,
            )
        )
        if not name_match and not content_shell:
            continue
        if not EXTENDS_PRODUCT_SHELL.search(text):
            bad.append(
                f"{rel}: base/layout shell must "
                "{% extends ...product_shell... %}"
            )
    assert not bad, (
        "Host base/layout must extend app-factory product_shell:\n"
        + "\n".join(bad)
    )


def test_no_host_copied_platform_chrome_templates():
    """Ban host copies of product_shell / shell_boot / theme_boot / platform_foot."""
    hits: list[str] = []
    for path in _iter_files(HTML_GLOBS + CODE_GLOBS):
        if path.name.lower() in BANNED_CHROME_FILENAMES:
            rel = path.relative_to(ROOT)
            hits.append(f"{rel}: host-copied platform chrome template")
    assert not hits, (
        "Do not copy product_shell / shell_boot / theme_boot / platform_foot "
        "into this repo — extend/include platform partials:\n"
        + "\n".join(hits)
    )


def test_logout_only_via_platform_session():
    """Logout in host HTML must go through platform_session (account surface)."""
    html_files = _html_files()
    if not html_files:
        return

    bad: list[str] = []
    for path in html_files:
        text = _read(path)
        if not LOGOUT_MARK.search(text):
            continue
        rel = path.relative_to(ROOT)
        # Allowed only when the file is/includes platform_session.
        name_ok = "platform_session" in path.name.lower()
        include_ok = bool(PLATFORM_SESSION_INCLUDE.search(text))
        if not (name_ok or include_ok):
            bad.append(
                f"{rel}: logout must only appear via platform_session include "
                "(account surface) — not custom nav/header chrome"
            )
    assert not bad, (
        "Logout only on account surface via platform_session:\n" + "\n".join(bad)
    )


def test_theme_locale_only_via_platform_partials():
    """Ban host theme-boot forks and reimplemented theme/locale chrome."""
    hits: list[str] = []
    for path in _iter_files(HTML_GLOBS + CODE_GLOBS):
        rel = path.relative_to(ROOT)
        rel_s = str(rel).replace("\\", "/")
        if HOST_THEME_LOCALE_REIMPL.search(rel_s):
            hits.append(f"{rel}: host theme/locale chrome reimplementation")
            continue
        text = _read(path)
        # Platform partial *includes* are fine; bare host theme boot is not.
        if HOST_THEME_BOOT_FORK.search(text):
            if re.search(
                r"""(?ix)
                platform_theme_locale
                |platform_controls
                |platform_asset_url
                |/static/platform/
                """,
                text,
            ):
                # File already wired to platform partials/assets — allow.
                continue
            hits.append(
                f"{rel}: host theme boot fork "
                "(use platform_theme_locale / platform_controls)"
            )
    assert not hits, (
        "Theme/locale only via platform partials "
        "(platform_theme_locale / platform_controls):\n" + "\n".join(hits)
    )
