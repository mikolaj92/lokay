"""Classify one factory-pass candidate as product, oil, or idle.

Oil is the canonical self mill (config ``incident_repo``, default
``mikolaj92/lokay``). Product is every other catalog repo. One pass is
oil XOR product; product wins when any product open issue or product
AI PR exists. ``work:ready`` / ``ai:ready`` are not admission gates.
"""

from __future__ import annotations

from typing import Any

from lokay.passkit.support import is_manual_pr

DEFAULT_SELF_REPO = "mikolaj92/lokay"
LANES = frozenset({"product", "oil", "idle"})


def self_repo(*sources: dict[str, Any] | None) -> str:
    """Canonical self id from begin/config; never a hardcoded path walk."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("incident_repo", "self_repo"):
            name = str(src.get(key) or "").strip()
            if name:
                return name
    return DEFAULT_SELF_REPO


def is_oil_repo(repo: str, *, self_id: str) -> bool:
    return bool(repo) and str(repo).strip() == str(self_id).strip()


def classify_repo_lane(repo: str, *, self_id: str) -> str:
    return "oil" if is_oil_repo(repo, self_id=self_id) else "product"


def _ready_rows(ready_by_repo: dict[str, Any] | None) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for repo, rows in dict(ready_by_repo or {}).items():
        name = str(repo or "").strip()
        if not name:
            continue
        kept = [row for row in list(rows or []) if isinstance(row, dict)]
        if kept:
            out[name] = kept
    return out


def _actionable_prs(prs_by_repo: dict[str, Any] | None) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for repo, rows in dict(prs_by_repo or {}).items():
        name = str(repo or "").strip()
        if not name:
            continue
        prs = [
            row
            for row in list(rows or [])
            if isinstance(row, dict) and not is_manual_pr(row)
        ]
        if prs:
            out[name] = prs
    return out


def product_candidates(
    *,
    ready_by_repo: dict[str, Any] | None = None,
    prs_by_repo: dict[str, Any] | None = None,
    self_id: str,
) -> bool:
    """True when a product open issue or product AI PR is waiting."""
    for repo in _ready_rows(ready_by_repo):
        if not is_oil_repo(repo, self_id=self_id):
            return True
    for repo in _actionable_prs(prs_by_repo):
        if not is_oil_repo(repo, self_id=self_id):
            return True
    return False


def oil_candidates(
    *,
    ready_by_repo: dict[str, Any] | None = None,
    prs_by_repo: dict[str, Any] | None = None,
    self_id: str,
) -> bool:
    for repo in _ready_rows(ready_by_repo):
        if is_oil_repo(repo, self_id=self_id):
            return True
    for repo in _actionable_prs(prs_by_repo):
        if is_oil_repo(repo, self_id=self_id):
            return True
    return False


def classify_pass_lane(
    *,
    self_id: str,
    ready_by_repo: dict[str, Any] | None = None,
    prs_by_repo: dict[str, Any] | None = None,
    clean_repos: list[str] | None = None,
    selected_repo: str = "",
) -> str:
    """Receipt lane: product wins, then oil, then idle."""
    chosen = str(selected_repo or "").strip()
    if not chosen:
        for repo in list(clean_repos or []):
            name = str(repo or "").strip()
            if name:
                chosen = name
                break
    if chosen:
        return classify_repo_lane(chosen, self_id=self_id)
    if product_candidates(
        ready_by_repo=ready_by_repo, prs_by_repo=prs_by_repo, self_id=self_id
    ):
        return "product"
    if oil_candidates(
        ready_by_repo=ready_by_repo, prs_by_repo=prs_by_repo, self_id=self_id
    ):
        return "oil"
    return "idle"
