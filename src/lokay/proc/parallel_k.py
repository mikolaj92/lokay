"""One job: pick at most K ready issues with one-per-repo mutex.

Stdin: JSON list ``[{repo, number}, ...]``.
Stdout: envelope ``{ok, selected: [...]}``. Deterministic: sort by repo, then
number. At most one issue per repo. Default K is 4.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.envelope import emit_exit, err, ok, read_stdin_json


def select_k(issues: list[Any], *, k: int) -> list[dict[str, Any]]:
    """Return up to *k* issues, earliest (repo, number) wins per repo."""
    rows: list[dict[str, Any]] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        repo = item.get("repo")
        number = item.get("number")
        if repo is None or number is None:
            continue
        try:
            rows.append({"repo": str(repo), "number": int(number)})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda row: (row["repo"], row["number"]))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        repo = str(row["repo"])
        if repo in seen:
            continue
        seen.add(repo)
        selected.append(row)
        if len(selected) >= k:
            break
    return selected


def run_parallel_k(payload: Any, *, k: int) -> dict[str, Any]:
    if payload is None:
        payload = []
    if not isinstance(payload, list):
        return err("stdin must be JSON list of {repo, number}")
    if k < 0:
        return err("k must be >= 0")
    return ok(selected=select_k(payload, k=k))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-parallel-k")
    parser.add_argument(
        "--k",
        type=int,
        default=4,
        help="max issues to select (one per repo; default 4)",
    )
    args = parser.parse_args(argv)
    try:
        payload = read_stdin_json()
    except json.JSONDecodeError:
        return emit_exit(err("stdin must be JSON list of {repo, number}"))
    return emit_exit(run_parallel_k(payload, k=int(args.k)))


if __name__ == "__main__":
    raise SystemExit(main())
