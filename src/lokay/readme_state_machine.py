"""README carries a generated Fala path index; the checker compares, never scrapes.

The authored contract is ``fala/lokay.fala-package.toml``. The README section
between the markers is a rendered artifact of it: verification regenerates the
table and compares strings exactly. Per-path design diagrams live in
``docs/FALA_PATHS.md``.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from lokay.graph_run import _project_root, find_default_package

BEGIN_MARKER = "<!-- fala-paths:begin (generated from fala/lokay.fala-package.toml) -->"
END_MARKER = "<!-- fala-paths:end -->"


def load_package_paths(package_path: Path | None = None) -> list[dict[str, str]]:
    """Authored path ids and titles, in package order."""
    pkg_file = package_path or find_default_package()
    data = tomllib.loads(pkg_file.read_text(encoding="utf-8"))
    return [
        {"id": str(p["id"]), "title": str(p.get("title") or "")}
        for p in data.get("correlation_paths", [])
    ]


def render_path_index(paths: list[dict[str, str]]) -> str:
    lines = ["| Ścieżka Fali | Tytuł |", "| --- | --- |"]
    for path in paths:
        lines.append(f"| `{path['id']}` | {path['title']} |")
    return "\n".join(lines)


def _readme_section(readme_text: str) -> str:
    begin = readme_text.index(BEGIN_MARKER) + len(BEGIN_MARKER)
    end = readme_text.index(END_MARKER)
    return readme_text[begin:end].strip()


def verify_readme_sync(
    package_path: Path | None = None,
    readme_path: Path | None = None,
) -> tuple[bool, list[str]]:
    root = _project_root()
    readme_file = readme_path or (root / "README.md")
    if not readme_file.is_file():
        return False, [f"README.md not found at {readme_file}"]

    readme_text = readme_file.read_text(encoding="utf-8")
    errors: list[str] = []

    try:
        section = _readme_section(readme_text)
    except ValueError:
        return False, [
            "README.md is missing the fala-paths markers; run: lokay-readme-check --write"
        ]

    expected = render_path_index(load_package_paths(package_path))
    if section != expected.strip():
        errors.append("README fala-paths section is stale; run: lokay-readme-check --write")

    workflows = root / ".github" / "workflows"
    if workflows.exists() and any(workflows.iterdir()):
        errors.append(
            "Repository contains .github/workflows; Lokay rules prohibit GitHub Actions workflows."
        )

    return not errors, errors


def write_readme_section(
    package_path: Path | None = None,
    readme_path: Path | None = None,
) -> None:
    """Regenerate the marked fala-paths section in place."""
    root = _project_root()
    readme_file = readme_path or (root / "README.md")
    text = readme_file.read_text(encoding="utf-8")
    rendered = (
        f"{BEGIN_MARKER}\n{render_path_index(load_package_paths(package_path))}\n{END_MARKER}"
    )
    try:
        begin = text.index(BEGIN_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        text = text[:begin] + rendered + text[end:]
    except ValueError:
        text = text.rstrip("\n") + "\n\n" + rendered + "\n"
    readme_file.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-readme-check")
    parser.add_argument("--check", action="store_true", help="Check synchronization and exit 1 if stale")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the marked fala-paths section in README.md",
    )
    parser.add_argument("--package", type=Path, help="Path to fala-package.toml")
    parser.add_argument("--readme", type=Path, help="Path to README.md")
    args = parser.parse_args(argv)

    if args.write:
        write_readme_section(package_path=args.package, readme_path=args.readme)
        print("README.md fala-paths section regenerated.")
        return 0

    ok, errors = verify_readme_sync(package_path=args.package, readme_path=args.readme)
    if not ok:
        print("README synchronization errors:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("README.md is synchronized with authored Fala state machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
