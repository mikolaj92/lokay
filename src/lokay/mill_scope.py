"""This mill's delivery catalog.

The live mini mill delivers mikolaj92/lokay only. Hermetic mill-physics
tests may use a catalog that does not include that name; those catalogs
are delivered as-is. Mixed catalogs that include the mill repo stay clamped.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

DEFAULT_MILL_REPO = "mikolaj92/lokay"
SKIP_REASON = "repo_not_delivered_by_mini_mill"


def mill_repo() -> str:
    raw = os.environ.get("LOKAY_MILL_REPO", "").strip()
    return raw or DEFAULT_MILL_REPO


def delivers(repo: str, *, mill: str | None = None) -> bool:
    name = str(repo or "").strip()
    return bool(name) and name == (mill or mill_repo())


def scoped_repos(
    repos: Iterable[str], *, mill: str | None = None
) -> tuple[list[str], list[str]]:
    """Return (deliver, skipped). Clamp only when mill is in the catalog."""
    target = mill or mill_repo()
    names = [str(r) for r in repos]
    if target in names:
        return [name for name in names if name == target], [
            name for name in names if name != target
        ]
    return names, []


def in_scope(repo: str, catalog: Iterable[str] | None = None, *, mill: str | None = None) -> bool:
    """Pass atoms: clamp mixed catalogs; empty catalog fails closed to mill."""
    name = str(repo or "").strip()
    if not name:
        return False
    names = [str(item) for item in catalog] if catalog is not None else []
    if not names:
        return delivers(name, mill=mill)
    deliver, _ = scoped_repos(names, mill=mill)
    return name in deliver
