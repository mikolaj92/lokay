"""Classify one nested coding_execution Fala envelope as a parent route."""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.envelope import emit_exit, err


def classify(child: dict[str, Any] | None) -> dict[str, Any]:
    """Always return ok=True with a route the parent when can read.

    A failed or empty nested Fala is route=empty, not process.failed.
    """
    blob = child if isinstance(child, dict) else {}
    if blob.get("ok") is True:
        return {
            "ok": True,
            "route": str(blob.get("route") or "human"),
            "decision": dict(blob.get("decision") or {}),
            "evidence_kind": str(blob.get("evidence_kind") or "none"),
            "reason": blob.get("reason"),
        }
    reason = blob.get("reason")
    if not isinstance(reason, str) or not reason:
        error = blob.get("error")
        reason = error if isinstance(error, str) and error else "coding_execution_empty"
    return {
        "ok": True,
        "route": "empty",
        "decision": {},
        "evidence_kind": "none",
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-classify-coding-execution")
    parser.add_argument("--child-json", required=True)
    args = parser.parse_args(argv)
    try:
        child = json.loads(args.child_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid child JSON: {exc}"))
    if not isinstance(child, dict):
        return emit_exit(err("child JSON object required"))
    return emit_exit(classify(child))


if __name__ == "__main__":
    raise SystemExit(main())
