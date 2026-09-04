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
    repos = {
        str(name).strip()
        for name in list(ready_by_repo) + list(inbox_by_repo)
        if str(name).strip()
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for repo in repos:
        covered = issue_numbers_covered_by_prs(
            list(prs_by_repo.get(repo) or []),
            branch_prefix=branch_prefix,
        )
        blocked = excluded_numbers(ledger, repo)
        rows = list(ready_by_repo.get(repo) or []) + list(
            inbox_by_repo.get(repo) or []
        )
        out[repo] = implementable_rows(rows, covered=covered, blocked=blocked)
    return out


def remaining_ready_count(work: dict[str, list[Any]] | None) -> int:
    return sum(len(rows or []) for rows in dict(work or {}).values())
