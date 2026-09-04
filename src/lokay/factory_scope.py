"""Configured delivery-catalog membership helpers.

The production lokay delivers every enabled repository in its configured catalog.
``LOKAY_REPO_SCOPE`` remains an optional single-repository override for isolated
canaries and hermetic tests; it is not the production default scope.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

DEFAULT_REPO_SCOPE = ""
SKIP_REASON = "repo_not_in_delivery_catalog"


def factory_repo() -> str:
    """Optional single-repository override. Empty means full configured catalog."""
    return os.environ.get("LOKAY_REPO_SCOPE", "").strip()


def delivers(
    repo: str,
    *,
    catalog: Iterable[str] | None = None,
    lokay: str | None = None,
) -> bool:
    name = str(repo or "").strip()
    if not name:
        return False
    target = lokay if lokay is not None else factory_repo()
    if target:
        return name == target
    names = {str(item).strip() for item in (catalog or ()) if str(item).strip()}
    return name in names


def scoped_repos(
    repos: Iterable[str], *, lokay: str | None = None
) -> tuple[list[str], list[str]]:
    """Return (delivered, skipped), preserving configured catalog order."""
    names = [str(repo).strip() for repo in repos if str(repo).strip()]
    target = lokay if lokay is not None else factory_repo()
    if not target:
        return names, []
    return [name for name in names if name == target], [
        name for name in names if name != target
    ]


def in_scope(
    repo: str,
    catalog: Iterable[str] | None = None,
    *,
    lokay: str | None = None,
) -> bool:
    """Return true only for a catalog member (or explicit single-repo override)."""
    return delivers(repo, catalog=catalog, lokay=lokay)
