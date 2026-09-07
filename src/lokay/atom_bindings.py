"""Explicit atom ownership primitives; resolving never executes a handler."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any, Iterable


class BindingError(ValueError):
    """Missing or ambiguous ownership must stop before any atom effect."""


@dataclass(frozen=True)
class Binding:
    name: str
    handler: Callable[..., Any]
    numbered: bool = False

    def matches(self, atom: str) -> bool:
        if not self.numbered:
            return atom == self.name
        if not atom.startswith(self.name):
            return False
        suffix = atom[len(self.name):]
        return suffix.isascii() and suffix.isdecimal() and not suffix.startswith("0")


def resolve(atom: str, bindings: Iterable[Binding]) -> Binding:
    """Return the sole owner, refusing exact/family overlaps too."""
    matches = [binding for binding in bindings if binding.matches(atom)]
    if not matches:
        raise BindingError(f"missing atom binding: {atom!r}")
    if len(matches) != 1:
        raise BindingError(f"conflicting atom bindings: {atom!r}")
    return matches[0]
