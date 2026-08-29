"""Catalog row: compose a task source with one code target.

Two fields. Missing field defaults to github and the same target.
Code is one plugin (repo + PR together). No separate prs field.
No executors. No adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_PLUGIN = "github"
KNOWN_PLUGINS = frozenset({"github", "azure"})
CATALOG_FIELDS = ("issues", "code")


class CatalogError(ValueError):
    """Illegal catalog row."""


@dataclass(frozen=True)
class CatalogBinding:
    """Plugin + target. One side of a catalog row."""

    plugin: str
    target: str

    def __post_init__(self) -> None:
        plugin = str(self.plugin or "").strip()
        target = str(self.target or "").strip()
        if not plugin:
            raise CatalogError("catalog plugin must be non-empty")
        if not target:
            raise CatalogError("catalog target must be non-empty")
        object.__setattr__(self, "plugin", plugin)
        object.__setattr__(self, "target", target)

    def __str__(self) -> str:
        return f"{self.plugin}:{self.target}"


@dataclass(frozen=True)
class CatalogRow:
    """One place: tasks composed with code. Code does not split into PR and repo."""

    issues: CatalogBinding
    code: CatalogBinding
    name: str = ""
    clone_path: str = ""


def compose_catalog(issues: CatalogBinding, code: CatalogBinding) -> CatalogRow:
    """Compose task source with code. Two targets may differ. PR stays on code."""
    return CatalogRow(issues=issues, code=code)


def _binding(raw: Any, *, default_target: str) -> CatalogBinding:
    if raw is None:
        return CatalogBinding(DEFAULT_PLUGIN, default_target)
    if not isinstance(raw, dict):
        raise CatalogError("issues/code must be a mapping")
    plugin = str(raw.get("plugin") or DEFAULT_PLUGIN).strip() or DEFAULT_PLUGIN
    target = str(raw.get("target") or default_target).strip()
    return CatalogBinding(plugin, target)


def parse_catalog_row(raw: dict[str, Any]) -> CatalogRow:
    """Parse one catalog row. Missing issues/code => github + the same target."""
    if not isinstance(raw, dict):
        raise CatalogError("catalog row must be a mapping")
    if "prs" in raw:
        raise CatalogError("catalog row has no separate prs field; PR goes with code")
    code_raw = raw.get("code")
    if isinstance(code_raw, dict) and "prs" in code_raw:
        raise CatalogError("catalog row has no separate prs field; PR goes with code")

    name = str(raw.get("name") or "").strip()
    issues_raw = raw.get("issues")
    code_target_hint = ""
    issues_target_hint = ""
    if isinstance(code_raw, dict):
        code_target_hint = str(code_raw.get("target") or "").strip()
    if isinstance(issues_raw, dict):
        issues_target_hint = str(issues_raw.get("target") or "").strip()
    default_target = name or code_target_hint or issues_target_hint
    if not default_target:
        raise CatalogError(
            "catalog row needs a target (name, issues.target, or code.target)"
        )

    issues = _binding(issues_raw, default_target=default_target)
    code = _binding(code_raw, default_target=default_target)

    if not name:
        if code.plugin == DEFAULT_PLUGIN:
            name = code.target
        elif issues.plugin == DEFAULT_PLUGIN:
            name = issues.target
        else:
            name = code.target

    clone = str(raw.get("clone_path") or "").strip()
    if not clone and isinstance(code_raw, dict):
        clone = str(code_raw.get("clone_path") or "").strip()

    return CatalogRow(issues=issues, code=code, name=name, clone_path=clone)


def assert_known_plugins(row: CatalogRow) -> None:
    """Fail closed when a plugin name is not known at load."""
    for side, binding in (("issues", row.issues), ("code", row.code)):
        if binding.plugin not in KNOWN_PLUGINS:
            known = ", ".join(sorted(KNOWN_PLUGINS))
            raise CatalogError(
                f"unknown catalog plugin {binding.plugin!r} on {side}; known: {known}"
            )
