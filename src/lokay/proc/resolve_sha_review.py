"""Select a fresh plugin review or verified same-SHA artifact cache."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from lokay.envelope import emit_exit, err
from lokay.review_boundary import resolve_structured_sha_review, resolve_sha_review


def resolve(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if evidence.get("task") and evidence.get("repo_path"):
        return resolve_structured_sha_review(evidence)
    return resolve_sha_review(evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-resolve-sha-review")
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid evidence JSON: {exc}"))
    if not isinstance(evidence, dict):
        return emit_exit(err("evidence object required"))
    return emit_exit(resolve(evidence))


if __name__ == "__main__":
    raise SystemExit(main())
