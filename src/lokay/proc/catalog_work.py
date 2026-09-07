"""Open catalog work: inbox ∪ ready. Lokay labels are not a gate."""

from __future__ import annotations

from typing import Any

from lokay.stuck import excluded_numbers, issue_numbers_covered_by_prs
from lokay.triage import is_open_work_issue


def issue_labels(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in list(row.get("labels") or []):
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item or "")
        if name:
            names.append(name)
    return names


def implementable_rows(
    rows: list[Any],
    *,
    covered: set[int] | None = None,
    blocked: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Keep open catalog issues. Human stops / covering PR / stuck exclude."""
    skip = set(covered or ()) | set(blocked or ())
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = int(row.get("number", -1))
        if number < 1 or number in seen or number in skip:
            continue
        if not is_open_work_issue(
            issue_labels(row),
            state=str(row.get("state") or "OPEN"),
        ):
            continue
        seen.add(number)
        out.append(row)
    return out


def work_by_repo(
    working: dict[str, Any] | None,
    *,
    stuck: dict[str, Any] | None = None,
    branch_prefix: str = "ai/fix/",
) -> dict[str, list[dict[str, Any]]]:
    """Union ready survey and inbox. ``work:ready`` is not a gate."""
    state = dict(working or {})
    ledger = dict(stuck if stuck is not None else state.get("stuck") or {})
    prs_by_repo = dict(state.get("prs_by_repo") or {})
    ready_by_repo = dict(state.get("ready_by_repo") or {})
    inbox_by_repo = dict(state.get("inbox_issues_by_repo") or {})
    leftover_ready = ready_by_repo_from_leftover(state.get("leftover_issues"))
    repos = {
        str(name).strip()
        for name in list(ready_by_repo) + list(inbox_by_repo) + list(leftover_ready)
        if str(name).strip()
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for repo in repos:
        covered = issue_numbers_covered_by_prs(
            list(prs_by_repo.get(repo) or []),
            branch_prefix=branch_prefix,
        )
        blocked = excluded_numbers(ledger, repo)
        rows = (
            list(ready_by_repo.get(repo) or [])
            + list(leftover_ready.get(repo) or [])
            + list(inbox_by_repo.get(repo) or [])
        )
        out[repo] = implementable_rows(rows, covered=covered, blocked=blocked)
    return out



def _as_issue_number(row: dict[str, Any]) -> int:
    for key in ("number", "issue"):
        try:
            number = int(row.get(key, -1))
        except (TypeError, ValueError):
            continue
        if number >= 1:
            return number
    return -1


def catalog_row_from_leftover(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a leftover queue row into a catalog ready row (``number`` key)."""
    if not isinstance(row, dict):
        return None
    number = _as_issue_number(row)
    if number < 1:
        return None
    out = dict(row)
    out["number"] = number
    if "issue" not in out:
        out["issue"] = number
    return out


def ready_by_repo_from_leftover(
    leftover_issues: list[Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Takeable dual-ready / ai:ready leftover rows grouped by repo (#1086)."""
    from lokay.proc.walk_issue_leftover import row_is_ready

    out: dict[str, list[dict[str, Any]]] = {}
    seen: dict[str, set[int]] = {}
    for raw in list(leftover_issues or []):
        if not isinstance(raw, dict) or not row_is_ready(raw):
            continue
        row = catalog_row_from_leftover(raw)
        if row is None:
            continue
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        number = int(row["number"])
        bucket = seen.setdefault(repo, set())
        if number in bucket:
            continue
        bucket.add(number)
        out.setdefault(repo, []).append(row)
    return out


def remaining_ready_count(work: dict[str, list[Any]] | None) -> int:
    return sum(len(rows or []) for rows in dict(work or {}).values())
