"""Atomic: refuse a plan-only git name list (no real code path).

Reads ``git diff --name-only`` from stdin or ``--names-file``. Exit 2 when the
list is empty or every path is under ``.lokay/`` (or otherwise has no code
path). Exit 0 when at least one path is under ``src/``, ``tests/``,
``scripts/``, or ``fala/``.

Mill contract: PRs #100/#104/#105 shipped plan-only (``.lokay/`` only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok

CODE_ROOTS = ("src", "tests", "scripts", "fala")
PLAN_ROOT = ".lokay"


def normalize_name(raw: str) -> str:
    text = raw.strip().strip('"').replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def parse_names(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        name = normalize_name(line)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def is_code_path(path: str) -> bool:
    return any(_under(path, root) for root in CODE_ROOTS)


def is_plan_path(path: str) -> bool:
    return _under(path, PLAN_ROOT)


def evaluate_names(names: list[str]) -> dict[str, Any]:
    """Classify a ``git diff --name-only`` listing. Fail closed without code."""
    code_paths = [n for n in names if is_code_path(n)]
    plan_paths = [n for n in names if is_plan_path(n)]
    other_paths = [n for n in names if n not in code_paths and n not in plan_paths]
    fields = {
        "names": names,
        "code_paths": code_paths,
        "plan_paths": plan_paths,
        "other_paths": other_paths,
    }
    if code_paths:
        return ok(reason="has_code", **fields)
    if not names:
        return err("empty diff: no paths", reason="empty", **fields)
    if not other_paths:
        return err(
            "plan-only diff: every path is under .lokay/",
            reason="plan_only",
            **fields,
        )
    return err(
        "no real code path (need src/, tests/, scripts/, or fala/)",
        reason="no_code",
        **fields,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-require-code-diff")
    parser.add_argument(
        "--names-file",
        default="",
        help="git diff --name-only listing (default: stdin)",
    )
    args = parser.parse_args(argv)
    if args.names_file:
        path = Path(args.names_file)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return emit_exit(err(f"cannot read --names-file: {exc}"))
    else:
        text = sys.stdin.read()
    payload = evaluate_names(parse_names(text))
    if payload.get("ok"):
        return emit_exit(payload)
    return emit_exit(payload, code=2)


if __name__ == "__main__":
    raise SystemExit(main())
