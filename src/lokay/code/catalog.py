"""Catalog field `code`: plugin + target + clone path.

Old rows (name + clone_path) are github and the same target.
Unknown plugins fail at load. No Azure. No tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lokay.code.contract import CodeContract, CodeContractError, bind_code

if TYPE_CHECKING:
    from lokay.config import Config
    from lokay.runner import Runner

KNOWN_CODE_PLUGINS = frozenset({"github"})


@dataclass(frozen=True)
class CodeSlot:
    """One catalog `code` field. Plugin + target + local path."""

    plugin: str
    target: str
    clone_path: Path

    def __post_init__(self) -> None:
        plugin = str(self.plugin or "").strip()
        target = str(self.target or "").strip()
        if not plugin:
            raise CodeContractError("code plugin must be non-empty")
        if not target:
            raise CodeContractError("code target must be non-empty")
        if plugin not in KNOWN_CODE_PLUGINS:
            raise CodeContractError(f"unknown code plugin: {plugin}")
        object.__setattr__(self, "plugin", plugin)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "clone_path", Path(self.clone_path))


def parse_code_slot(
    raw: dict[str, Any],
    *,
    default_name: str,
    default_clone: Path,
) -> CodeSlot:
    """Read catalog field `code`. Missing field is github + name."""
    name = str(default_name or "").strip()
    clone = Path(default_clone)
    code = raw.get("code") if isinstance(raw, dict) else None
    if code is None:
        return CodeSlot(plugin="github", target=name, clone_path=clone)
    if not isinstance(code, dict):
        raise CodeContractError("code must be a mapping")
    plugin = str(code.get("plugin") or "github").strip()
    target = str(code.get("target") or name).strip()
    if code.get("clone_path"):
        clone = Path(code["clone_path"])
    return CodeSlot(plugin=plugin, target=target, clone_path=clone)


def slot_from_repo(repo: Any) -> CodeSlot:
    """Code slot from a catalog row or RepoConfig. Old rows stay github."""
    plugin = str(getattr(repo, "code_plugin", None) or "github").strip()
    target = str(getattr(repo, "code_target", None) or getattr(repo, "name", "") or "").strip()
    raw_clone = getattr(repo, "clone_path", None)
    clone = Path(raw_clone) if raw_clone else Path("/tmp/lokay-code-unused")
    code = getattr(repo, "code", None)
    if isinstance(code, CodeSlot):
        return code
    if isinstance(code, dict):
        return parse_code_slot(
            {"code": code, "name": target},
            default_name=target,
            default_clone=clone,
        )
    return CodeSlot(plugin=plugin, target=target, clone_path=clone)


def load_code(
    slot: CodeSlot,
    *,
    runner: Runner,
    config: Config,
    live: bool,
) -> CodeContract:
    """Load the code plugin named by the catalog `code` field."""
    if slot.plugin != "github":
        raise CodeContractError(f"unknown code plugin: {slot.plugin}")
    from lokay.code.github import GithubCode

    host = GithubCode.from_slot(slot, runner=runner, config=config, live=live)
    return bind_code(host.target, repo=host.repo, pr=host.pr)
