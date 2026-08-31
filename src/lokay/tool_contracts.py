"""Mechanical loading of one self-contained agent contract per tool."""

from __future__ import annotations

import re
from importlib.resources import files
from typing import Any

_FIELD = re.compile(r"<<([a-z][a-z0-9_]*)>>")


class ContractError(ValueError):
    """A tool contract is missing or cannot be rendered exactly."""


def render_contract(tool: str, /, **values: Any) -> str:
    if not tool or any(part in tool for part in ("/", "\\", "..")):
        raise ContractError(f"invalid tool contract name: {tool!r}")
    resource = files("lokay").joinpath("tool_contracts", tool, "prompt.md")
    try:
        template = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise ContractError(f"contract not found: {tool}") from exc

    fields = set(_FIELD.findall(template))
    provided = set(values)
    missing = sorted(fields - provided)
    unknown = sorted(provided - fields)
    if missing:
        raise ContractError(f"{tool} contract missing values: {missing}")
    if unknown:
        raise ContractError(f"{tool} contract unknown values: {unknown}")
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"<<{key}>>", str(value))
    if _FIELD.search(rendered):
        raise ContractError(f"cannot render {tool} contract")
    return rendered
