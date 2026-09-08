"""Verification and synchronization of README.md Mermaid diagrams with authored Fala paths."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from lokay.graph_run import find_default_package, _project_root


def load_package_paths(package_path: Path | None = None) -> dict[str, dict[str, Any]]:
    pkg_file = package_path or find_default_package()
    data = tomllib.loads(pkg_file.read_text(encoding="utf-8"))
    paths = {}
    for p in data.get("correlation_paths", []):
        path_id = str(p["id"])
        effectors = []
        for eff in p.get("effectors", []):
            effectors.append({
                "id": str(eff["id"]),
                "atom": str((eff.get("config") or {}).get("atom") or ""),
                "conduction": [str(c) for c in eff.get("conduction", [])],
                "when": dict(eff.get("when") or {}),
            })
        paths[path_id] = {
            "id": path_id,
            "title": str(p.get("title") or ""),
            "description": str(p.get("description") or ""),
            "effectors": effectors,
        }
    return paths


def parse_readme_documented_paths(readme_text: str) -> set[str]:
    pattern = r"\| `[^`]+` \| `([a-z0-9_]+)` \|"
    return set(re.findall(pattern, readme_text))


def parse_readme_mermaid_nodes(readme_text: str) -> set[str]:
    pattern = r"```mermaid\nstateDiagram-v2\n(.*?)```"
    mermaid_blocks = re.findall(pattern, readme_text, re.DOTALL)
    nodes = set()
    for block in mermaid_blocks:
        for line in block.splitlines():
            line = line.strip()
            if "-->" in line:
                parts = line.split("-->")
                src = parts[0].strip()
                dst = parts[1].split(":")[0].strip()
                if src and src != "[*]":
                    nodes.add(src)
                if dst and dst != "[*]":
                    nodes.add(dst)
    return nodes


def verify_readme_sync(
    package_path: Path | None = None,
    readme_path: Path | None = None,
) -> tuple[bool, list[str]]:
    root = _project_root()
    readme_file = readme_path or (root / "README.md")
    if not readme_file.is_file():
        return False, [f"README.md not found at {readme_file}"]

    readme_text = readme_file.read_text(encoding="utf-8")
    pkg_paths = load_package_paths(package_path)

    errors = []

    # 1. Verify every authored correlation path is documented in README path table
    documented_paths = parse_readme_documented_paths(readme_text)
    authored_paths = set(pkg_paths.keys())
    missing_paths = authored_paths - documented_paths
    if missing_paths:
        errors.append(f"Authored Fala paths missing from README path table: {sorted(missing_paths)}")

    # 2. Verify headings use authored Fala path IDs
    heading_pattern = r"^### ([^\\n]+?) — `([a-z0-9_]+)`$"
    headings = dict(re.findall(heading_pattern, readme_text, re.MULTILINE))
    heading_path_ids = set(headings.values())
    invalid_headings = heading_path_ids - authored_paths
    if invalid_headings:
        errors.append(f"README section headings use invalid Fala path IDs: {sorted(invalid_headings)}")

    # 3. Verify no GitHub Actions workflows exist
    workflows = root / ".github" / "workflows"
    if workflows.exists() and any(workflows.iterdir()):
        errors.append("Repository contains .github/workflows; Lokay rules prohibit GitHub Actions workflows.")

    return len(errors) == 0, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-readme-check")
    parser.add_argument("--check", action="store_true", help="Check synchronization and exit 1 if stale")
    parser.add_argument("--package", type=Path, help="Path to fala-package.toml")
    parser.add_argument("--readme", type=Path, help="Path to README.md")
    args = parser.parse_args(argv)

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
